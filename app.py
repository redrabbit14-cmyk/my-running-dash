import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일 (S25 등 모바일 기기에서 가로 배치 강제)
st.markdown("""
<style>
    /* 기본 배경 및 패딩 */
    .main { background-color: #f9fafb; padding: 5px !important; }
    
    /* [핵심] 모바일에서도 컬럼을 가로로 유지 */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important; /* 줄바꿈 절대 방지 */
        width: 100% !important;
        gap: 5px !important;
    }
    
    /* 각 컬럼의 너비를 4등분 */
    [data-testid="column"] {
        width: 24% !important;
        flex: 1 1 24% !important;
        min-width: 0px !important; /* 최소 너비 제한 해제 */
    }

    .section-card { background: white; border-radius: 8px; padding: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); margin-bottom: 10px; }
    
    /* 크루 사진 크기 축소 (S25 화면 폭에 맞춤) */
    .crew-photo { width: 50px; height: 50px; border-radius: 50%; margin: 0 auto 5px; object-fit: cover; border: 2px solid #3b82f6; display: block; }
    .crew-avatar { width: 50px; height: 50px; border-radius: 50%; background: #e5e7eb; margin: 0 auto 5px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
    
    /* 스탯 박스 컴팩트화 */
    .crew-stat-box { border-radius: 4px; padding: 3px 1px; margin: 2px 0; font-size: 10px; text-align: center; display: flex; flex-direction: column; justify-content: center; background: #f8fafc; }
    .stat-label { font-size: 8px; color: #64748b; font-weight: 600; }
    .stat-value { font-size: 10px; font-weight: 700; color: #0f172a; }
</style>
""", unsafe_allow_html=True)

# 3. 유틸리티 및 데이터 로직 (기존과 동일)
def mps_to_pace_str(mps):
    if not mps or mps <= 0: return "N/A"
    sec = 1000 / mps
    return f"{int(sec // 60)}:{int(sec % 60):02d}"

def pace_to_seconds(p):
    try:
        parts = str(p).split(':')
        return int(float(parts[0]) * 60 + float(parts[1]))
    except: return None

def seconds_to_pace(s):
    if not s or s <= 0: return "N/A"
    return f"{int(s // 60)}:{int(s % 60):02d}"

@st.cache_data(ttl=600)
def fetch_data():
    try:
        res = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28"}, json={"page_size": 50})
        rows = []
        for r in res.json().get("results", []):
            p = r.get("properties", {})
            files = p.get("사진", {}).get("files", [])
            img = files[0].get("file", {}).get("url") if files and files[0].get("type") == "file" else (files[0].get("external", {}).get("url") if files else None)
            
            rows.append({
                "날짜": p.get("날짜", {}).get("date", {}).get("start", "")[:10],
                "러너": p.get("러너", {}).get("select", {}).get("name", "Unknown"),
                "거리": p.get("거리", {}).get("number", 0) if (p.get("거리", {}).get("number") or 0) < 100 else p.get("거리", {}).get("number", 0)/1000,
                "페이스": mps_to_pace_str(p.get("페이스", {}).get("number")),
                "사진": img
            })
        df = pd.DataFrame(rows)
        df['날짜'] = pd.to_datetime(df['날짜'])
        return df
    except: return pd.DataFrame()

# --- 메인 실행 ---
df = fetch_data()
if df.empty: st.stop()

st.title("🏃 러닝 크루 대시보드")

# 총거리 요약 (매우 작게)
tw_start = (datetime.now() - timedelta(days=(datetime.now().weekday() + 1) % 7)).replace(hour=0,minute=0)
tw_dist = df[df['날짜'] >= tw_start]['거리'].sum()
st.markdown(f'<div style="text-align:center; font-weight:700; color:#047857; margin-bottom:10px;">이번 주: {tw_dist:.2f} km</div>', unsafe_allow_html=True)

# 크루 컨디션 - S25에서도 무조건 가로 4열 배치
cols = st.columns(4)
crew_list = ["용남", "재탁", "주현", "유재"]

for i, member in enumerate(crew_list):
    with cols[i]:
        m_all = df[df['러너'] == member].head(7)
        
        # 가중 평균 페이스
        avg_p = "N/A"
        if not m_all.empty:
            m_all['p_sec'] = m_all['페이스'].apply(pace_to_seconds)
            v = m_all.dropna(subset=['p_sec', '거리'])
            if not v.empty:
                avg_p = seconds_to_pace((v['p_sec'] * v['거리']).sum() / v['거리'].sum())
        
        # 사진 표시
        pic = m_all['사진'].dropna().iloc[0] if not m_all['사진'].dropna().empty else None
        if pic: st.markdown(f'<img src="{pic}" class="crew-photo">', unsafe_allow_html=True)
        else: st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
        
        # 이름 및 통계 요약 (좁은 폭에 최적화)
        st.markdown(f'<div style="text-align:center; font-size:11px; font-weight:800;">{member}</div>', unsafe_allow_html=True)
        
        m_tw = df[(df['러너']==member) & (df['날짜']>=tw_start)]['거리'].sum()
        st.markdown(f'<div class="crew-stat-box"><div class="stat-label">이번주</div><div class="stat-value">{m_tw:.1f}k</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="crew-stat-box"><div class="stat-label">페이스</div><div class="stat-value">{avg_p}</div></div>', unsafe_allow_html=True)
