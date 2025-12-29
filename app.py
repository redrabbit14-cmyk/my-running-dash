import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일 (가장 안정적이었던 초기 스타일로 회귀)
st.markdown("""
<style>
    .main { background-color: #f9fafb; padding: 10px; }
    .section-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px; }
    .total-distance-card { background: linear-gradient(to bottom right, #ecfdf5, #d1fae5); border: 2px solid #86efac; border-radius: 12px; padding: 20px; text-align: center; }
    .crew-photo { width: 100px; height: 100px; border-radius: 50%; margin: 0 auto 10px; object-fit: cover; border: 3px solid #3b82f6; display: block; }
    .crew-avatar { width: 100px; height: 100px; border-radius: 50%; background: #e5e7eb; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; font-size: 40px; }
    .crew-stat-box { border-radius: 8px; padding: 8px 4px; margin: 5px 0; font-size: 12px; text-align: center; min-height: 50px; display: flex; flex-direction: column; justify-content: center; }
    .stat-label { font-size: 10px; color: #6b7280; font-weight: 600; margin-bottom: 2px; }
    .stat-value { font-size: 14px; font-weight: 700; color: #1f2937; }
</style>
""", unsafe_allow_html=True)

# 3. 유틸리티 함수
def mps_to_pace_str(mps):
    try:
        if mps is None or mps <= 0: return "N/A"
        total_seconds = 1000 / mps
        return f"{int(total_seconds // 60)}:{int(total_seconds % 60):02d}"
    except: return "N/A"

def pace_to_seconds(pace_str):
    try:
        if not pace_str or pd.isna(pace_str) or pace_str == "N/A": return None
        parts = str(pace_str).split(':')
        return int(float(parts[0]) * 60 + float(parts[1]))
    except: return None

def seconds_to_pace(seconds):
    if seconds is None or pd.isna(seconds) or seconds <= 0: return "N/A"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"

@st.cache_data(ttl=600)
def fetch_notion_data():
    try:
        response = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
            json={"page_size": 100}
        )
        data = []
        for row in response.json().get("results", []):
            props = row.get("properties", {})
            date_obj = props.get("날짜", {}).get("date", {})
            if not date_obj: continue
            
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            dist_val = 0
            for f in ["실제 거리", "거리", "Distance"]:
                v = props.get(f, {}).get("number")
                if v is not None:
                    dist_val = v if v < 100 else v / 1000
                    break
            
            mps = props.get("페이스", {}).get("number")
            
            photo_url = None
            files = props.get("사진", {}).get("files", [])
            if files:
                f_obj = files[0]
                photo_url = f_obj.get("file", {}).get("url") if f_obj.get("type") == "file" else f_obj.get("external", {}).get("url")

            data.append({
                "날짜": date_obj.get("start")[:10],
                "러너": runner, "거리": dist_val, "페이스": mps_to_pace_str(mps),
                "사진": photo_url, "생성시간": row.get("created_time", "")
            })
        df = pd.DataFrame(data)
        df['날짜'] = pd.to_datetime(df['날짜'])
        return df.sort_values(['날짜'], ascending=False)
    except: return pd.DataFrame()

# --- 실행 ---
df = fetch_notion_data()
if df.empty: st.stop()

st.title("🏃 러닝 크루 대시보드")

# 주간 요약
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
this_week_start = today - timedelta(days=(today.weekday() + 1) % 7)
tw = df[df['날짜'] >= this_week_start]

st.markdown(f'''
    <div class="section-card">
        <div class="total-distance-card">
            <div style="font-size:16px; color:#047857; font-weight:600;">이번 주 크루 합산 총거리</div>
            <div style="font-size:48px; font-weight:800; color:#047857;">{tw['거리'].sum():.2f} km</div>
        </div>
    </div>
''', unsafe_allow_html=True)

# 크루 리스트 (안정적인 4컬럼 구성)
st.markdown('<div class="section-card"><div style="font-size:18px; font-weight:700; margin-bottom:15px;">👥 크루 컨디션</div>', unsafe_allow_html=True)
crew_list = ["용남", "재탁", "주현", "유재"]
cols = st.columns(len(crew_list))

for i, member in enumerate(crew_list):
    with cols[i]:
        m_all = df[df['러너'] == member].head(7)
        
        # 가중 평균 페이스 계산
        avg_pace = "N/A"
        if not m_all.empty:
            m_all['p_sec'] = m_all['페이스'].apply(pace_to_seconds)
            v = m_all.dropna(subset=['p_sec', '거리'])
            if not v.empty:
                avg_pace = seconds_to_pace((v['p_sec'] * v['거리']).sum() / v['거리'].sum())
        
        # 사진
        pic = m_all['사진'].dropna().iloc[0] if not m_all['사진'].dropna().empty else None
        if pic: st.markdown(f'<img src="{pic}" class="crew-photo">', unsafe_allow_html=True)
        else: st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
        
        st.markdown(f'<div style="text-align:center; font-weight:700; margin-bottom:10px;">{member}</div>', unsafe_allow_html=True)
        
        m_tw_dist = tw[tw['러너'] == member]['거리'].sum()
        st.markdown(f'<div class="crew-stat-box" style="background:#f0f9ff;"><div class="stat-label">이번주 거리</div><div class="stat-value">{m_tw_dist:.2f} km</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="crew-stat-box" style="background:#f5f3ff;"><div class="stat-label">평균 페이스(7회)</div><div class="stat-value">{avg_pace}</div></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
