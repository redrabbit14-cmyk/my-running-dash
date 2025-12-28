import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일 (디자인 유지)
st.markdown("""
<style>
    .main { background-color: #f9fafb; padding: 10px; }
    .section-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px; }
    .total-distance-card { background: linear-gradient(to bottom right, #ecfdf5, #d1fae5); border: 2px solid #86efac; border-radius: 12px; padding: 20px; text-align: center; }
    .crew-photo { width: 80px; height: 80px; border-radius: 50%; margin: 0 auto 10px; object-fit: cover; border: 3px solid #3b82f6; display: block; }
    .crew-avatar { width: 80px; height: 80px; border-radius: 50%; background: #e5e7eb; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; font-size: 32px; }
    .crew-stat-box { border-radius: 6px; padding: 6px 4px; margin: 4px 0; font-size: 12px; text-align: center; }
    .stat-label { font-size: 10px; color: #6b7280; font-weight: 600; }
    .stat-value { font-size: 14px; font-weight: 700; color: #1f2937; }
    .insight-box { background: white; border-left: 4px solid; border-radius: 8px; padding: 10px; margin: 6px 0; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
    .insight-distance { border-color: #f59e0b; background: #fffbeb; }
    .insight-elevation { border-color: #8b5cf6; background: #faf5ff; }
    .insight-pace { border-color: #10b981; background: #f0fdf4; }
</style>
""", unsafe_allow_html=True)

# 3. 데이터 파싱 보강 (페이스 0:02 에러 해결)
def parse_pace(p_prop):
    try:
        if p_prop.get("type") == "number" and p_prop.get("number"):
            val = p_prop["number"]
            # 만약 초 단위(예: 330)라면 -> 5:30
            if val > 100: return f"{int(val//60)}:{int(val%60):02d}"
            # 만약 소수점 분 단위(예: 5.5)라면 -> 5:30
            else: return f"{int(val)}:{int((val%1)*60):02d}"
        elif p_prop.get("type") == "rich_text" and p_prop["rich_text"]:
            return p_prop["rich_text"][0]["plain_text"]
    except: pass
    return "N/A"

@st.cache_data(ttl=300)
def fetch_notion_data():
    try:
        response = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
            json={}
        )
        if not response.ok: return pd.DataFrame()
        
        data = []
        for row in response.json().get("results", []):
            props = row.get("properties", {})
            date_raw = props.get("날짜", {}).get("date", {}).get("start") if props.get("날짜") else None
            
            dist = 0
            for k in ["실제 거리", "거리"]:
                if props.get(k, {}).get("number"):
                    dist = props[k]["number"]
                    if dist > 100: dist /= 1000
                    break
            
            pace = "N/A"
            for k in ["평균 페이스", "페이스"]:
                if props.get(k):
                    pace = parse_pace(props[k])
                    if pace != "N/A": break
            
            data.append({
                "날짜": date_raw, 
                "러너": props.get("러너", {}).get("select", {}).get("name", "Unknown"),
                "거리": dist,
                "고도": props.get("고도", {}).get("number", 0) or 0,
                "페이스": pace,
                "사진": props.get("사진", {}).get("files", [{}])[0].get("file", {}).get("url") or props.get("사진", {}).get("files", [{}])[0].get("external", {}).get("url") if props.get("사진", {}).get("files") else None
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            # 날짜 변환 시 시간대(Timezone) 제거하여 에러 방지
            df['날짜'] = pd.to_datetime(df['날짜']).dt.tz_localize(None)
            df = df.dropna(subset=['날짜'])
        return df
    except: return pd.DataFrame()

# 페이스 비교용 초 환산
def pace_to_seconds(pace_str):
    if not pace_str or ":" not in str(pace_str): return 9999
    try:
        m, s = map(int, str(pace_str).split(':'))
        return m * 60 + s
    except: return 9999

# --- 메인 실행 ---
df = fetch_notion_data()

if not df.empty:
    st.title("🏃 러닝 크루 대시보드")
    
    # [섹션 1] 주간 요약 (날짜 비교 에러 수정 버전)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tw_start = today - timedelta(days=today.weekday())
    lw_start = tw_start - timedelta(days=7)
    
    tw = df[df['날짜'] >= tw_start]
    lw = df[(df['날짜'] >= lw_start) & (df['날짜'] < tw_start)]
    
    total_dist = tw['거리'].sum()
    prev_dist = lw['거리'].sum()
    p_change = ((total_dist - prev_dist) / prev_dist * 100) if prev_dist > 0 else 0
    
    st.markdown(f'''
        <div class="section-card">
            <div class="total-distance-card">
                <div style="font-size:42px;font-weight:800;color:#047857;">{total_dist:.1f} km</div>
                <div style="font-size:14px;color:#6b7280;">이번 주 크루 합산 (전주 대비 {p_change:+.1f}%)</div>
            </div>
        </div>
    ''', unsafe_allow_html=True)

    # [섹션 2] 크루 컨디션
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:18px; font-weight:700; margin-bottom:15px;">👥 크루 컨디션</div>', unsafe_allow_html=True)
    
    crew_list = df['러너'].unique()
    cols = st.columns(len(crew_list[:4]))
    
    for idx, member in enumerate(crew_list[:4]):
        m_tw = tw[tw['러너'] == member]
        m_lw = lw[lw['러너'] == member]
        
        d_val = m_tw['거리'].sum()
        p_val = m_lw['거리'].sum()
        m_change = ((d_val - p_val) / p_val * 100) if p_val > 0 else 0
        pace_val = m_tw.sort_values('날짜', ascending=False)['페이스'].iloc[0] if not m_tw.empty else "N/A"
        photo_val = df[df['러너'] == member].sort_values('날짜', ascending=False)['사진'].dropna().iloc[0] if not df[df['러너'] == member]['사진'].dropna().empty else None
        
        with cols[idx]:
            if photo_val: st.markdown(f'<img src="{photo_val}" class="crew-photo">', unsafe_allow_html=True)
            else: st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align:center; font-weight:700; margin-bottom:10px;">{member}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="crew-stat-box" style="background:#dbeafe;"><div class="stat-label">주간 거리</div><div class="stat-value">{d_val:.1f}km</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="crew-stat-box" style="background:#dcfce7;"><div class="stat-label">전주 대비</div><div class="stat-value">{m_change:+.1f}%</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="crew-stat-box" style="background:#f3e8ff;"><div class="stat-label">평균 페이스</div><div class="stat-value">{pace_val}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # [섹션 3] Insights & Fun (고도, 스피드 복구)
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:18px; font-weight:700; margin-bottom:15px;">🏆 Insights & Fun</div>', unsafe_allow_html=True)
    
    if not tw.empty:
        # 1. 최장 거리
        top_d = tw.groupby('러너')['거리'].sum()
        st.markdown(f'<div class="insight-box insight-distance">🥇 최장 거리 주자: <b>{top_d.idxmax()} ({top_d.max():.1f}km)</b></div>', unsafe_allow_html=True)
        
        # 2. 최고 고도
        top_e = tw.groupby('러너')['고도'].sum()
        if top_e.max() > 0:
            st.markdown(f'<div class="insight-box insight-elevation">⛰️ 최고 고도 정복자: <b>{top_e.idxmax()} ({top_e.max():.0f}m)</b></div>', unsafe_allow_html=True)
        
        # 3. 최고 스피드
        tw_copy = tw.copy()
        tw_copy['p_sec'] = tw_copy['페이스'].apply(pace_to_seconds)
        tw_valid = tw_copy[tw_copy['p_sec'] < 1200]
        if not tw_valid.empty:
            fastest = tw_valid.loc[tw_valid['p_sec'].idxmin()]
            st.markdown(f'<div class="insight-box insight-pace">⚡ 최고 스피드 러너: <b>{fastest["러너"]} ({fastest["페이스"]}/km)</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
