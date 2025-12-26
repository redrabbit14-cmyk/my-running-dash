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

# 프로토타입 스타일 CSS
st.markdown("""
<style>
    .main { 
        background-color: #f9fafb;
        padding: 20px;
    }
    
    /* 섹션 카드 */
    .section-card {
        background: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 24px;
    }
    
    /* 공지사항 박스 */
    .notice-box {
        background: #eff6ff;
        border: 2px solid #bfdbfe;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
        font-size: 14px;
        color: #1e40af;
    }
    
    /* 날씨 카드 */
    .weather-card {
        background: linear-gradient(to bottom, #e0f2fe, #f0f9ff);
        border-radius: 8px;
        padding: 8px;
        text-align: center;
        font-size: 12px;
    }
    
    /* 총 거리 카드 */
    .total-distance-card {
        background: linear-gradient(to bottom right, #ecfdf5, #d1fae5);
        border: 2px solid #86efac;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    
    /* 크루원 카드 */
    .crew-card {
        background: white;
        border: 2px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        transition: all 0.3s;
        height: 100%;
    }
    
    .crew-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transform: translateY(-2px);
    }
    
    .crew-avatar {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        background: linear-gradient(135deg, #3b82f6, #60a5fa);
        margin: 0 auto 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 36px;
        border: 4px solid white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .crew-stat-box {
        background: #f3f4f6;
        border-radius: 6px;
        padding: 8px;
        margin: 4px 0;
        font-size: 13px;
    }
    
    /* Insight & Fun 박스 */
    .insight-box {
        background: white;
        border-left: 4px solid;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    
    .insight-full { border-color: #10b981; background: #f0fdf4; }
    .insight-climb { border-color: #3b82f6; background: #eff6ff; }
    .insight-speed { border-color: #a855f7; background: #faf5ff; }
    
    /* AI 추천 박스 */
    .ai-box {
        background: linear-gradient(to bottom right, #faf5ff, #ede9fe);
        border: 2px solid #c4b5fd;
        border-radius: 12px;
        padding: 24px;
    }
    
    /* 제목 스타일 */
    .section-title {
        font-size: 24px;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 20px;
    }
    
    .subsection-title {
        font-size: 18px;
        font-weight: 600;
        color: #374151;
        margin-bottom: 12px;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(135deg, #a855f7, #9333ea);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #9333ea, #7e22ce);
        box-shadow: 0 4px 12px rgba(168,85,247,0.4);
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
                    # m 단위를 km로 변환
                    dist = v["number"] / 1000 if v["number"] > 100 else v["number"]
                if "고도" in k and v.get("number") is not None:
                    elev = v["number"]
                if "페이스" in k or "pace" in k.lower():
                    if v.get("rich_text") and len(v["rich_text"]) > 0:
                        pace = v["rich_text"][0].get("plain_text", "")
                # 사진 URL 추출 (파일 또는 URL 속성)
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

def get_ai_recommendation(crew_summary):
    try:
        prompt = f"""당신은 전문 러닝 코치입니다. 다음 러닝 크루의 이번 주 데이터를 분석하고, 다음 주를 위한 맞춤형 훈련 계획을 추천해주세요.

{crew_summary}

다음 내용을 포함하여 친근하고 동기부여가 되는 톤으로 추천해주세요:
1. 크루 전체 분석 (2-3문장)
2. 다음 주 훈련 추천 (구체적인 거리, 페이스, 요일 포함)
3. 개인별 주의사항 (필요한 경우)
4. 응원 메시지

400자 이내로 작성해주세요."""

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

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.markdown('<div class="subsection-title">🏃 마라톤 대회 신청 안내</div>', unsafe_allow_html=True)
    st.markdown('<div class="notice-box">부산 벚꽃마라톤 - 신청기간: 1/10 ~ 2/15</div>', unsafe_allow_html=True)
    st.markdown('<div class="notice-box">경남 진해 군항제 마라톤 - 신청기간: 2/1 ~ 3/10</div>', unsafe_allow_html=True)
    st.markdown('<div class="notice-box">부산 낙동강 마라톤 - 신청기간: 1/20 ~ 2/28</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="subsection-title">🌤️ 주간 날씨</div>', unsafe_allow_html=True)
    weather_cols = st.columns(7)
    weather_data = [
        ('월', '☀️', '5°'), ('화', '☁️', '3°'), ('수', '🌧️', '2°'),
        ('목', '☁️', '4°'), ('금', '☀️', '6°'), ('토', '☀️', '7°'), ('일', '⛅', '5°')
    ]
    for i, (day, icon, temp) in enumerate(weather_data):
        with weather_cols[i]:
            st.markdown(f'''
                <div class="weather-card">
                    <div style="font-weight:600;color:#475569;margin-bottom:4px;">{day}</div>
                    <div style="font-size:24px;margin:4px 0;">{icon}</div>
                    <div style="font-weight:700;color:#1e293b;">{temp}</div>
                </div>
            ''', unsafe_allow_html=True)

with col3:
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
                <div style="font-size:48px;font-weight:800;color:#047857;margin-bottom:8px;">
                    {total_dist:.1f}<span style="font-size:24px;color:#6b7280;"> km</span>
                </div>
                <div style="font-size:14px;color:#6b7280;margin-bottom:12px;">
                    목표: 200km
                </div>
                <div style="font-size:14px;font-weight:600;color:{trend_color};">
                    {trend_icon} 전주 대비 {percent_change:+.0f}%
                </div>
            </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown('<div class="total-distance-card"><div style="color:#6b7280;">데이터 로딩 중...</div></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ========== 중단: 크루 컨디션 ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)

if not df.empty:
    crew_members = df['러너'].unique()[:4]
    crew_cols = st.columns(4)
    
    for idx, member in enumerate(crew_members):
        with crew_cols[idx]:
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
                avg_pace = this_week_data['페이스'].mode()[0] if len(this_week_data['페이스'].mode()) > 0 else "5:30"
            
            last_run = this_week_data['날짜'].max() if not this_week_data.empty else None
            rest_days = (datetime.now() - last_run).days if last_run and pd.notna(last_run) else 0
            
            trend_icon = "📈" if dist_change >= 0 else "📉"
            trend_color = "#10b981" if dist_change >= 0 else "#ef4444"
            
            # 사진 URL 가져오기 (가장 최근 런의 사진 사용)
            photo_url = None
            if not member_data.empty and '사진' in member_data.columns:
                recent_photos = member_data[member_data['사진'].notna()].sort_values('날짜', ascending=False)
                if not recent_photos.empty:
                    photo_url = recent_photos.iloc[0]['사진']
            
            # 아바타 표시 (사진 있으면 사진, 없으면 이모지)
            if photo_url:
                avatar_html = f'<img src="{photo_url}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:4px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.1);">'
            else:
                avatar_html = '<div class="crew-avatar">👤</div>'
            
            # 크루원 카드 - HTML을 단일 블록으로 작성
            card_html = f"""
            <div class="crew-card">
                {avatar_html}
                <h3 style="font-size:18px;font-weight:700;color:#1f2937;margin:12px 0 16px 0;">{member}</h3>
                <div class="crew-stat-box" style="background:#dbeafe;">
                    <div style="font-size:11px;color:#6b7280;">주간거리</div>
                    <div style="font-size:16px;font-weight:700;color:#1e40af;">{week_dist:.1f} km</div>
                </div>
                <div class="crew-stat-box">
                    <div style="font-size:11px;color:#6b7280;">전주 대비</div>
                    <div style="font-size:14px;font-weight:700;color:{trend_color};">{trend_icon} {dist_change:+.0f}%</div>
                </div>
                <div class="crew-stat-box" style="background:#f3e8ff;">
                    <div style="font-size:11px;color:#6b7280;">평균속도</div>
                    <div style="font-size:14px;font-weight:700;color:#7c3aed;">{avg_pace}/km</div>
                </div>
                <div class="crew-stat-box" style="background:#fed7aa;">
                    <div style="font-size:11px;color:#6b7280;">연속휴식</div>
                    <div style="font-size:14px;font-weight:700;color:#ea580c;">{rest_days}일</div>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
else:
    st.info("노션 데이터를 불러올 수 없습니다. NOTION_TOKEN과 DATABASE_ID를 확인해주세요.")

st.markdown('</div>', unsafe_allow_html=True)

# ========== 하단: Insight & Fun ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🎉 Insight & Fun</div>', unsafe_allow_html=True)

if not df.empty:
    this_week = calculate_week_data(df, 0)
    
    # 사실상 풀
    full_runners = this_week[this_week['거리'] >= 20].sort_values('거리', ascending=False)
    if not full_runners.empty:
        full_text = ", ".join([
            f"<b style='color:#10b981;'>{row['러너']}</b>({row['거리']:.0f}K, {row['날짜'].strftime('%m/%d')})"
            for _, row in full_runners.iterrows()
        ])
        st.markdown(f'''
            <div class="insight-box insight-full">
                <div style="display:flex;align-items:center;gap:12px;">
                    <span style="font-size:32px;">🏃‍♂️</span>
                    <div>
                        <h3 style="font-size:18px;font-weight:700;color:#1f2937;margin:0 0 4px 0;">사실상 풀</h3>
                        <p style="margin:0;color:#374151;">{full_text}</p>
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    # 사실상 등산
    top_climb = this_week.loc[this_week['고도'].idxmax()] if not this_week.empty and this_week['고도'].sum() > 0 else None
    if top_climb is not None:
        st.markdown(f'''
            <div class="insight-box insight-climb">
                <div style="display:flex;align-items:center;gap:12px;">
                    <span style="font-size:32px;">⛰️</span>
                    <div>
                        <h3 style="font-size:18px;font-weight:700;color:#1f2937;margin:0 0 4px 0;">사실상 등산</h3>
                        <p style="margin:0;color:#374151;">
                            <b style='color:#3b82f6;'>{top_climb['러너']}</b>({top_climb['고도']:.0f}m, {top_climb['날짜'].strftime('%m/%d')})
                        </p>
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
    
    # 사실상 우사인볼트 (페이스 데이터가 있을 경우)
    if '페이스' in this_week.columns and this_week['페이스'].notna().any():
        fastest = this_week.loc[this_week['페이스'].idxmin()]
        st.markdown(f'''
            <div class="insight-box insight-speed">
                <div style="display:flex;align-items:center;gap:12px;">
                    <span style="font-size:32px;">⚡</span>
                    <div>
                        <h3 style="font-size:18px;font-weight:700;color:#1f2937;margin:0 0 4px 0;">사실상 우사인볼트</h3>
                        <p style="margin:0;color:#374151;">
                            <b style='color:#a855f7;'>{fastest['러너']}</b>({fastest['페이스']}/km, {fastest['날짜'].strftime('%m/%d')})
                        </p>
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ========== AI 훈련 추천 ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="ai-box">', unsafe_allow_html=True)

col_ai1, col_ai2 = st.columns([3, 1])
with col_ai1:
    st.markdown('<div style="display:flex;align-items:center;gap:8px;"><span style="font-size:28px;">✨</span><span class="section-title" style="margin:0;">AI 코치 훈련 추천</span></div>', unsafe_allow_html=True)
with col_ai2:
    if st.button("✨ 추천 받기", use_container_width=True):
        if not df.empty:
            this_week = calculate_week_data(df, 0)
            summary = f"""
[크루 데이터]
- 총 거리: {this_week['거리'].sum():.1f}km
- 크루원: {', '.join(df['러너'].unique())}
- 20km+ 달성자: {len(this_week[this_week['거리'] >= 20])}명
"""
            with st.spinner("AI가 분석 중입니다..."):
                recommendation = get_ai_recommendation(summary)
                st.session_state['ai_recommendation'] = recommendation

if 'ai_recommendation' in st.session_state:
    st.markdown(f'''
        <div style="background:white;border-radius:8px;padding:20px;margin-top:16px;border:2px solid #c4b5fd;">
            <p style="line-height:1.8;color:#374151;white-space:pre-wrap;">{st.session_state['ai_recommendation']}</p>
        </div>
    ''', unsafe_allow_html=True)
else:
    st.markdown('''
        <div style="background:white;border-radius:8px;padding:40px;margin-top:16px;text-align:center;border:2px solid #e9d5ff;">
            <span style="font-size:48px;display:block;margin-bottom:12px;">✨</span>
            <p style="color:#6b7280;margin:0;">위 버튼을 눌러 AI 코치의 맞춤형 훈련 추천을 받아보세요!</p>
        </div>
    ''', unsafe_allow_html=True)

st.markdown('</div></div>', unsafe_allow_html=True)
