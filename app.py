import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

# 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 모바일 최적화 CSS
st.markdown("""
<style>
    .main { 
        background-color: #f9fafb;
        padding: 10px;
    }
    
    .section-card {
        background: white;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 16px;
    }
    
    .notice-box {
        background: #eff6ff;
        border: 2px solid #bfdbfe;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 6px;
        font-size: 13px;
        color: #1e40af;
    }
    
    .weather-card {
        background: linear-gradient(to bottom, #e0f2fe, #f0f9ff);
        border-radius: 6px;
        padding: 6px 2px;
        text-align: center;
        font-size: 11px;
    }
    
    .total-distance-card {
        background: linear-gradient(to bottom right, #ecfdf5, #d1fae5);
        border: 2px solid #86efac;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    
    .insight-box {
        background: white;
        border-left: 4px solid;
        border-radius: 8px;
        padding: 12px;
        margin: 6px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    
    .insight-full { border-color: #10b981; background: #f0fdf4; }
    .insight-climb { border-color: #3b82f6; background: #eff6ff; }
    .insight-speed { border-color: #a855f7; background: #faf5ff; }
    
    .ai-box {
        background: linear-gradient(to bottom right, #faf5ff, #ede9fe);
        border: 2px solid #c4b5fd;
        border-radius: 12px;
        padding: 16px;
    }
    
    .section-title {
        font-size: 20px;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 12px;
    }
    
    .subsection-title {
        font-size: 15px;
        font-weight: 600;
        color: #374151;
        margin-bottom: 8px;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #a855f7, #9333ea);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def fetch_notion_data():
    try:
        if not NOTION_TOKEN or not DATABASE_ID:
            return pd.DataFrame()
        
        notion = Client(auth=NOTION_TOKEN)
        response = notion.databases.query(database_id=DATABASE_ID)
        results = response.get("results", [])
        data = []
        
        for row in results:
            props = row.get("properties", {})
            
            date_val = ""
            if props.get("날짜", {}).get("date"):
                date_val = props["날짜"]["date"].get("start", "")[:10]
            
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            dist = 0
            elev = 0
            pace = None
            photo_url = None
            
            for k, v in props.items():
                if "거리" in k and v.get("number") is not None:
                    dist = v["number"] / 1000 if v["number"] > 100 else v["number"]
                if "고도" in k and v.get("number") is not None:
                    elev = v["number"]
                if "페이스" in k or "pace" in k.lower():
                    if v.get("rich_text") and len(v["rich_text"]) > 0:
                        pace = v["rich_text"][0].get("plain_text", "")
                if ("사진" in k or "photo" in k.lower() or "이미지" in k or "image" in k.lower()):
                    if v.get("files") and len(v["files"]) > 0:
                        photo_url = v["files"][0].get("file", {}).get("url") or v["files"][0].get("external", {}).get("url")
                    elif v.get("url"):
                        photo_url = v["url"]
            
            data.append({
                "날짜": date_val,
                "러너": runner,
                "거리": dist,
                "고도": elev,
                "페이스": pace,
                "사진": photo_url
            })
        
        df = pd.DataFrame(data)
        if not df.empty and '날짜' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'])
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

def calculate_week_data(df, weeks_ago=0):
    if df.empty:
        return pd.DataFrame()
    
    end_date = datetime.now() - timedelta(days=weeks_ago * 7)
    start_date = end_date - timedelta(days=7)
    
    return df[(df['날짜'] >= start_date) & (df['날짜'] < end_date)]

def get_ai_recommendation(crew_data):
    try:
        crew_summary = "\n".join([
            f"- {m['name']}: 주간 {m['distance']:.1f}km, 평균페이스 {m['pace']}, 연속휴식 {m['rest_days']}일"
            for m in crew_data
        ])
        
        prompt = f"""당신은 전문 러닝 코치입니다. 다음 4명의 크루원에 대해 각각 1-2줄의 간단한 훈련 조언을 해주세요.

{crew_summary}

각 크루원마다:
- 현재 상태 간단 평가
- 다음 주 구체적인 훈련 조언 (거리, 페이스, 휴식 등)

형식:
**크루원이름**: 조언 내용 (1-2줄)

친근하고 동기부여가 되는 톤으로 작성해주세요."""

        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'Content-Type': 'application/json'},
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 1000,
                'messages': [{'role': 'user', 'content': prompt}]
            }
        )
        
        if response.ok:
            data = response.json()
            return data['content'][0]['text']
        return "추천을 생성할 수 없습니다."
    except Exception as e:
        return f"AI 추천 생성 중 오류 발생: {str(e)}"

# 데이터 로드
df = fetch_notion_data()

# ========== 상단: 크루 현황 ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)

# 1. 마라톤 대회 신청 안내
st.markdown('<div class="subsection-title">🏃 마라톤 대회 신청 안내</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">부산 벚꽃마라톤 - 신청: 1/10~2/15</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">경남 진해 군항제 마라톤 - 신청: 2/1~3/10</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">부산 낙동강 마라톤 - 신청: 1/20~2/28</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 2. 주간 날씨 (7일 가로 배치)
st.markdown('<div class="subsection-title">🌤️ 주간 날씨</div>', unsafe_allow_html=True)
weather_data = [
    ('월', '☀️', '5°'), ('화', '☁️', '3°'), ('수', '🌧️', '2°'),
    ('목', '☁️', '4°'), ('금', '☀️', '6°'), ('토', '☀️', '7°'), ('일', '⛅', '5°')
]
weather_html = '<div style="display:flex;gap:4px;justify-content:space-between;">'
for day, icon, temp in weather_data:
    weather_html += f'''
        <div class="weather-card" style="flex:1;min-width:0;">
            <div style="font-weight:600;color:#475569;font-size:10px;">{day}</div>
            <div style="font-size:20px;margin:2px 0;">{icon}</div>
            <div style="font-weight:700;color:#1e293b;font-size:11px;">{temp}</div>
        </div>
    '''
weather_html += '</div>'
st.markdown(weather_html, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 3. 총 거리 (크루 합산)
st.markdown('<div class="subsection-title">🎯 총 거리 (크루 합산)</div>', unsafe_allow_html=True)

if not df.empty:
    this_week = calculate_week_data(df, 0)
    last_week = calculate_week_data(df, 1)
    
    total_dist = this_week['거리'].sum()
    prev_dist = last_week['거리'].sum()
    
    if prev_dist > 0:
        percent_change = ((total_dist - prev_dist) / prev_dist) * 100
    else:
        percent_change = 0
    
    trend_icon = "📈" if percent_change >= 0 else "📉"
    trend_color = "#10b981" if percent_change >= 0 else "#ef4444"
    
    st.markdown(f'''
        <div class="total-distance-card">
            <div style="font-size:40px;font-weight:800;color:#047857;margin-bottom:6px;">
                {total_dist:.1f}<span style="font-size:20px;color:#6b7280;"> km</span>
            </div>
            <div style="font-size:13px;color:#6b7280;margin-bottom:8px;">
                지난주: {prev_dist:.1f}km
            </div>
            <div style="font-size:14px;font-weight:600;color:{trend_color};">
                {trend_icon} 전주 대비 {percent_change:+.0f}%
            </div>
        </div>
    ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ========== 중단: 크루 컨디션 (4명 가로배치) ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)

if not df.empty:
    crew_members = df['러너'].unique()[:4]
    crew_data_for_ai = []
    
    cols = st.columns(4)
    
    for idx, member in enumerate(crew_members):
        member_data = df[df['러너'] == member]
        this_week_data = calculate_week_data(member_data, 0)
        last_week_data = calculate_week_data(member_data, 1)
        
        week_dist = this_week_data['거리'].sum()
        prev_week_dist = last_week_data['거리'].sum()
        
        if prev_week_dist > 0:
            dist_change = ((week_dist - prev_week_dist) / prev_week_dist) * 100
        else:
            dist_change = 0
        
        avg_pace = "5:30"
        if not this_week_data.empty and this_week_data['페이스'].notna().any():
            paces = this_week_data['페이스'].dropna()
            if len(paces) > 0:
                avg_pace = paces.mode()[0] if len(paces.mode()) > 0 else paces.iloc[0]
        
        last_run = this_week_data['날짜'].max() if not this_week_data.empty else None
        rest_days = (datetime.now() - last_run).days if last_run and pd.notna(last_run) else 0
        
        crew_data_for_ai.append({
            'name': member,
            'distance': week_dist,
            'pace': avg_pace,
            'rest_days': rest_days
        })
        
        trend_icon = "📈" if dist_change >= 0 else "📉"
        trend_color = "#10b981" if dist_change >= 0 else "#ef4444"
        
        # 사진 URL
        photo_url = None
        if not member_data.empty and '사진' in member_data.columns:
            recent_photos = member_data[member_data['사진'].notna()].sort_values('날짜', ascending=False)
            if not recent_photos.empty:
                photo_url = recent_photos.iloc[0]['사진']
        
        with cols[idx]:
            if photo_url:
                st.markdown(f'<img src="{photo_url}" style="width:50px;height:50px;border-radius:50%;object-fit:cover;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin:0 auto;display:block;">', unsafe_allow_html=True)
            else:
                st.markdown('<div style="width:50px;height:50px;border-radius:50%;background:linear-gradient(135deg,#3b82f6,#60a5fa);margin:0 auto;display:flex;align-items:center;justify-content:center;font-size:24px;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.1);">👤</div>', unsafe_allow_html=True)
            
            st.markdown(f'<h3 style="font-size:13px;font-weight:700;color:#1f2937;margin:8px 0;text-align:center;">{member}</h3>', unsafe_allow_html=True)
            
            st.markdown(f'''
                <div style="background:#dbeafe;border-radius:4px;padding:4px;margin:2px 0;text-align:center;">
                    <div style="font-size:9px;color:#6b7280;">주간거리</div>
                    <div style="font-size:12px;font-weight:700;color:#1e40af;">{week_dist:.1f}km</div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
                <div style="background:#f3f4f6;border-radius:4px;padding:4px;margin:2px 0;text-align:center;">
                    <div style="font-size:9px;color:#6b7280;">전주대비</div>
                    <div style="font-size:11px;font-weight:700;color:{trend_color};">{trend_icon} {dist_change:+.0f}%</div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
                <div style="background:#f3e8ff;border-radius:4px;padding:4px;margin:2px 0;text-align:center;">
                    <div style="font-size:9px;color:#6b7280;">평균속도</div>
                    <div style="font-size:11px;font-weight:700;color:#7c3aed;">{avg_pace}/km</div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
                <div style="background:#fed7aa;border-radius:4px;padding:4px;margin:2px 0;text-align:center;">
                    <div style="font-size:9px;color:#6b7280;">연속휴식</div>
                    <div style="font-size:11px;font-weight:700;color:#ea580c;">{rest_days}일</div>
                </div>
            ''', unsafe_allow_html=True)
    
    st.session_state['crew_data_for_ai'] = crew_data_for_ai

st.markdown('</div>', unsafe_allow_html=True)

# ========== 하단: Insight & Fun ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🎉 Insight & Fun</div>', unsafe_allow_html=True)

if not df.empty:
    this_week = calculate_week_data(df, 0)
    
    # 사실상 풀
    if not this_week.empty and this_week['거리'].sum() > 0:
        longest_run = this_week.loc[this_week['거리'].idxmax()]
        st.markdown(f'''
            <div class="insight-box insight-full">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-size:28px;">🏃‍♂️</span>
                    <div>
                        <h3 style="font-size:16px;font-weight:700;color:#1f2937;margin:0 0 4px 0;">사실상 풀</h3>
                        <p style="margin:0;color:#374151;font-size:14px;">
                            <b style='color:#10b981;'>{longest_run['러너']}</b> {longest_run['거리']:.1f}km ({longest_run['날짜'].strftime('%m/%d')})
                        </p>
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    # 사실상 등산
    if not this_week.empty and this_week['고도'].sum() > 0:
        top_climb = this_week.loc[this_week['고도'].idxmax()]
        st.markdown(f'''
            <div class="insight-box insight-climb">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-size:28px;">⛰️</span>
                    <div>
                        <h3 style="font-size:16px;font-weight:700;color:#1f2937;margin:0 0 4px 0;">사실상 등산</h3>
                        <p style="margin:0;color:#374151;font-size:14px;">
                            <b style='color:#3b82f6;'>{top_climb['러너']}</b> {top_climb['고도']:.0f}m ({top_climb['날짜'].strftime('%m/%d')})
                        </p>
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    # 사실상 우사인볼트
    if '페이스' in this_week.columns:
        paces_data = this_week[this_week['페이스'].notna()].copy()
        if not paces_data.empty:
            def pace_to_seconds(pace_str):
                try:
                    if isinstance(pace_str, str) and ':' in pace_str:
                        parts = pace_str.split(':')
                        return int(parts[0]) * 60 + int(parts[1])
                    return 999999
                except:
                    return 999999
            
            paces_data['페이스_초'] = paces_data['페이스'].apply(pace_to_seconds)
            fastest = paces_data.loc[paces_data['페이스_초'].idxmin()]
            
            st.markdown(f'''
                <div class="insight-box insight-speed">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="font-size:28px;">⚡</span>
                        <div>
                            <h3 style="font-size:16px;font-weight:700;color:#1f2937;margin:0 0 4px 0;">사실상 우사인볼트</h3>
                            <p style="margin:0;color:#374151;font-size:14px;">
                                <b style='color:#a855f7;'>{fastest['러너']}</b> {fastest['페이스']}/km ({fastest['날짜'].strftime('%m/%d')})
                            </p>
                        </div>
                    </div>
                </div>
            ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ========== AI 훈련 추천 ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="ai-box">', unsafe_allow_html=True)

st.markdown('<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;"><span style="font-size:24px;">✨</span><span class="section-title" style="margin:0;">AI 코치 훈련 추천</span></div>', unsafe_allow_html=True)

if st.button("✨ 추천 받기"):
    if 'crew_data_for_ai' in st.session_state:
        with st.spinner("AI가 분석 중입니다..."):
            recommendation = get_ai_recommendation(st.session_state['crew_data_for_ai'])
            st.session_state['ai_recommendation'] = recommendation

if 'ai_recommendation' in st.session_state:
    st.markdown(f'''
        <div style="background:white;border-radius:8px;padding:16px;margin-top:12px;border:2px solid #c4b5fd;">
            <div style="line-height:1.8;color:#374151;white-space:pre-wrap;font-size:14px;">{st.session_state['ai_recommendation']}</div>
        </div>
    ''', unsafe_allow_html=True)
else:
    st.markdown('''
        <div style="background:white;border-radius:8px;padding:30px;margin-top:12px;text-align:center;border:2px solid #e9d5ff;">
            <span style="font-size:40px;display:block;margin-bottom:8px;">✨</span>
            <p style="color:#6b7280;margin:0;font-size:13px;">위 버튼을 눌러 AI 코치의 맞춤형 훈련 추천을 받아보세요!</p>
        </div>
    ''', unsafe_allow_html=True)

st.markdown('</div></div>', unsafe_allow_html=True)
