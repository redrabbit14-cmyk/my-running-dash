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

# 모바일 최적화 CSS (날씨 관련 스타일 제거)
st.markdown("""
<style>
    .main { 
        background-color: #f9fafb;
        padding: 10px;
    }
    
    /* 섹션 카드 */
    .section-card {
        background: white;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 16px;
    }
    
    /* 공지사항 박스 */
    .notice-box {
        background: #eff6ff;
        border: 2px solid #bfdbfe;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 6px;
        font-size: 13px;
        color: #1e40af;
    }
    
    /* 총 거리 카드 */
    .total-distance-card {
        background: linear-gradient(to bottom right, #ecfdf5, #d1fae5);
        border: 2px solid #86efac;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    
    /* 크루원 카드 - 모바일용 간소화 */
    .crew-card {
        background: white;
        border: 2px solid #e5e7eb;
        border-radius: 10px;
        padding: 10px 8px;
        text-align: center;
        height: 100%;
    }
    
    .crew-avatar {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, #3b82f6, #60a5fa);
        margin: 0 auto 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        border: 3px solid white;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    
    .crew-stat-box {
        background: #f3f4f6;
        border-radius: 4px;
        padding: 6px 4px;
        margin: 3px 0;
        font-size: 11px;
    }
    
    /* Insight & Fun 박스 */
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
    
    /* AI 추천 박스 */
    .ai-box {
        background: linear-gradient(to bottom right, #faf5ff, #ede9fe);
        border: 2px solid #c4b5fd;
        border-radius: 12px;
        padding: 16px;
    }
    
    /* 제목 스타일 */
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
        
        prompt = f"""당신은 전문 러닝 코치입니다. 다음 크루원들에게 1-2줄의 간단한 조언을 해주세요.\n\n{crew_summary}"""

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
            return response.json()['content'][0]['text']
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

# 2. 총 거리 (크루 합산)
st.markdown('<div class="subsection-title">🎯 이번 주 크루 활동량</div>', unsafe_allow_html=True)

if not df.empty:
    this_week = calculate_week_data(df, 0)
    last_week = calculate_week_data(df, 1)
    
    total_dist = this_week['거리'].sum()
    prev_dist = last_week['거리'].sum()
    
    percent_change = ((total_dist - prev_dist) / prev_dist * 100) if prev_dist > 0 else 0
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

# ========== 중단: 크루 컨디션 ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)

if not df.empty:
    crew_members = df['러너'].unique()[:4]
    crew_cols = st.columns(4)
    crew_data_for_ai = []
    
    for idx, member in enumerate(crew_members):
        with crew_cols[idx]:
            member_data = df[df['러너'] == member]
            tw = calculate_week_data(member_data, 0)
            lw = calculate_week_data(member_data, 1)
            
            w_dist = tw['거리'].sum()
            lw_dist = lw['거리'].sum()
            d_change = ((w_dist - lw_dist) / lw_dist * 100) if lw_dist > 0 else 0
            
            avg_p = "5:30"
            if not tw.empty and tw['페이스'].notna().any():
                avg_p = tw['페이스'].dropna().mode()[0] if not tw['페이스'].dropna().mode().empty else tw['페이스'].dropna().iloc[0]
            
            l_run = tw['날짜'].max() if not tw.empty else None
            r_days = (datetime.now() - l_run).days if l_run and pd.notna(l_run) else 0
            
            crew_data_for_ai.append({'name': member, 'distance': w_dist, 'pace': avg_p, 'rest_days': r_days})
            
            p_url = None
            if not member_data.empty and '사진' in member_data.columns:
                recent = member_data[member_data['사진'].notna()].sort_values('날짜', ascending=False)
                if not recent.empty: p_url = recent.iloc[0]['사진']
            
            avatar = f'<img src="{p_url}" style="width:60px;height:60px;border-radius:50%;object-fit:cover;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.1);">' if p_url else '<div class="crew-avatar">👤</div>'
            
            st.markdown(f"""
            <div class="crew-card">
                {avatar}
                <h3 style="font-size:15px;font-weight:700;color:#1f2937;margin:8px 0 10px 0;">{member}</h3>
                <div class="crew-stat-box" style="background:#dbeafe;"><div style="font-size:10px;">주간거리</div><div style="font-size:14px;font-weight:700;">{w_dist:.1f}km</div></div>
                <div class="crew-stat-box"><div style="font-size:10px;">전주대비</div><div style="font-size:12px;font-weight:700;color:{"#10b981" if d_change>=0 else "#ef4444"};">{d_change:+.0f}%</div></div>
                <div class="crew-stat-box" style="background:#f3e8ff;"><div style="font-size:10px;">페이스</div><div style="font-size:12px;font-weight:700;">{avg_p}</div></div>
            </div>
            """, unsafe_allow_html=True)
    st.session_state['crew_data_for_ai'] = crew_data_for_ai

st.markdown('</div>', unsafe_allow_html=True)

# ========== 하단: Insight & AI 코치 ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🎉 Insight & AI 코치</div>', unsafe_allow_html=True)

if not df.empty:
    this_week = calculate_week_data(df, 0)
    if not this_week.empty:
        # 사실상 풀 (최장거리)
        longest = this_week.loc[this_week['거리'].idxmax()]
        st.markdown(f'<div class="insight-box insight-full"><b>🏆 사실상 풀:</b> {longest["러너"]} ({longest["거리"]:.1f}km)</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if st.button("✨ AI 코치에게 추천 받기"):
    if 'crew_data_for_ai' in st.session_state:
        with st.spinner("분석 중..."):
            st.session_state['ai_recommendation'] = get_ai_recommendation(st.session_state['crew_data_for_ai'])

if 'ai_recommendation' in st.session_state:
    st.markdown(f'<div class="ai-box">{st.session_state["ai_recommendation"]}</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
