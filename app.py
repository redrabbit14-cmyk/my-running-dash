import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일 (2x2 배치 및 모바일 최적화)
st.markdown("""
<style>
    .main { background-color: #f9fafb; padding: 10px !important; }
    
    /* 모바일에서 2열로 배치되도록 설정 */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-wrap: wrap !important; /* 2명 뒤에 다음 줄로 넘어가게 함 */
            gap: 10px !important;
        }
        [data-testid="column"] {
            width: calc(50% - 10px) !important; /* 화면의 절반 차지 */
            flex: 1 1 calc(50% - 10px) !important;
            min-width: calc(50% - 10px) !important;
        }
    }

    .section-card { background: white; border-radius: 12px; padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 10px; text-align: center; }
    .crew-photo { width: 70px; height: 70px; border-radius: 50%; margin: 0 auto 8px; object-fit: cover; border: 3px solid #3b82f6; display: block; }
    .crew-avatar { width: 70px; height: 70px; border-radius: 50%; background: #e5e7eb; margin: 0 auto 8px; display: flex; align-items: center; justify-content: center; font-size: 30px; }
    
    .stat-box { background: #f8fafc; border-radius: 8px; padding: 6px; margin-top: 5px; }
    .stat-label { font-size: 10px; color: #64748b; font-weight: 600; margin-bottom: 2px; }
    .stat-value { font-size: 13px; font-weight: 700; color: #1e293b; }
</style>
""", unsafe_allow_html=True)

# 3. 데이터 처리 함수 (가중 평균 로직 유지)
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
            headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28"}, json={"page_size": 100})
        rows = []
        for r in res.json().get("results", []):
            p = r.get("properties", {})
            files = p.get("사진", {}).get("files", [])
            img = None
            if files:
                f = files[0]
                img = f.get("file", {}).get("url") if f.get("type") == "file" else f.get("external", {}).get("url")
            
            rows.append({
                "날짜": p.get("날짜", {}).get("date", {}).get("start", "")[:10],
                "러너": p.get("러너", {}).get("select", {}).get("name", "Unknown"),
                "거리": p.get("거리", {}).get("number", 0) if (p.get("거리", {}).get("number") or 0) < 100 else p.get("거리", {}).get("number", 0)/1000,
                "페이스": mps_to_pace_str(p.get("페이스", {}).get("number")),
                "사진": img
            })
        df = pd.DataFrame(rows)
        df['날짜'] = pd.to_datetime(df['날짜'])
        return df.sort_values(['날짜'], ascending=False)
    except: return pd.DataFrame()

# --- 실행 ---
df = fetch_data()
if df.empty: st.stop()

st.title("🏃 러닝 크루 대시보드")

# 상단 요약
tw_start = (datetime.now() - timedelta(days=(datetime.now().weekday() + 1) % 7)).replace(hour=0,minute=0)
tw_dist = df[df['날짜'] >= tw_start]['거리'].sum()
st.markdown(f'<div style="background:#ecfdf5; padding:15px; border-radius:12px; text-align:center; margin-bottom:15px; border:1px solid #86efac;">'
            f'<div style="font-size:14px; color:#047857;">이번 주 합산 거리</div>'
            f'<div style="font-size:24px; font-weight:800; color:#065f46;">{tw_dist:.2f} km</div></div>', unsafe_allow_html=True)

# 크루 카드 배치 (2x2 격자)
crew_list = ["용남", "재탁", "주현", "유재"]
cols = st.columns(4) # 코드는 4개지만 CSS가 모바일에서 2개씩 끊어줌

for i, member in enumerate(crew_list):
    with cols[i]:
        m_all = df[df['러너'] == member].head(7)
        
        # 가중 평균 페이스 계산
        avg_p = "N/A"
        if not m_all.empty:
            m_all['p_sec'] = m_all['페이스'].apply(pace_to_seconds)
            v = m_all.dropna(subset=['p_sec', '거리'])
            if not v.empty:
                avg_p = seconds_to_pace((v['p_sec'] * v['거리']).sum() / v['거리'].sum())
        
        # 카드 디자인 시작
        st.markdown(f'<div class="section-card">', unsafe_allow_html=True)
        
        # 사진 (최신 링크 유지)
        pic = m_all['사진'].dropna().iloc[0] if not m_all['사진'].dropna().empty else None
        if pic: st.markdown(f'<img src="{pic}" class="crew-photo">', unsafe_allow_html=True)
        else: st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
        
        st.markdown(f'<div style="font-weight:800; font-size:16px; margin-bottom:8px;">{member}</div>', unsafe_allow_html=True)
        
        # 통계 정보
        m_tw = df[(df['러너']==member) & (df['날짜']>=tw_start)]['거리'].sum()
        st.markdown(f'<div class="stat-box"><div class="stat-label">이번주</div><div class="stat-value">{m_tw:.1f}km</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-box"><div class="stat-label">7회 평균</div><div class="stat-value">{avg_p}</div></div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
