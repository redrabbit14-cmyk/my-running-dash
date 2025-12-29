import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide")

# 2. CSS 스타일 (모바일에서 큼직하게 보이도록 카드 디자인 수정)
st.markdown("""
<style>
    .main { background-color: #f9fafb; }
    .section-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .total-distance-card { background: linear-gradient(to right, #ecfdf5, #d1fae5); border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #86efac; }
    
    /* 크루 카드 디자인 */
    .member-card { border: 1px solid #e5e7eb; border-radius: 15px; padding: 15px; margin-bottom: 10px; background: white; text-align: center; }
    .crew-photo { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 3px solid #3b82f6; margin: 0 auto 10px; }
    .crew-name { font-size: 18px; font-weight: 800; color: #1f2937; margin-bottom: 10px; }
    
    /* 스탯 박스 (세로형에서는 조금 더 시원하게 배치) */
    .stat-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px thin #f3f4f6; }
    .stat-label { color: #6b7280; font-size: 13px; font-weight: 600; }
    .stat-value { color: #111827; font-size: 14px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# 3. 데이터 로직 (가중 평균 및 사진 링크 만료 해결 포함)
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
            # 사진 추출 로직 최적화
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
                "고도": p.get("고도", {}).get("number", 0),
                "사진": img
            })
        df = pd.DataFrame(rows)
        df['날짜'] = pd.to_datetime(df['날짜'])
        return df
    except: return pd.DataFrame()

# --- 실행 ---
df = fetch_data()
if df.empty: st.stop()

st.title("🏃 러닝 크루 대시보드")

# 총거리 요약
tw_start = datetime.now() - timedelta(days=(datetime.now().weekday() + 1) % 7)
tw_dist = df[df['날짜'] >= tw_start.replace(hour=0,minute=0)]['거리'].sum()
st.markdown(f'<div class="total-distance-card"><h3>이번 주 크루 합산: {tw_dist:.2f} km</h3></div>', unsafe_allow_html=True)

st.write("") # 간격

# 크루 컨디션 - 가로/세로 자동 전환 레이아웃
crew_list = ["용남", "재탁", "주현", "유재"]
cols = st.columns(len(crew_list)) # PC에선 가로, 모바일에선 자동으로 세로 전환됨

for i, member in enumerate(crew_list):
    with cols[i]:
        m_data = df[df['러너'] == member].head(7)
        
        # 가중 평균 페이스 계산
        avg_pace = "N/A"
        if not m_data.empty:
            m_data['p_sec'] = m_data['페이스'].apply(pace_to_seconds)
            valid = m_data.dropna(subset=['p_sec', '거리'])
            if not valid.empty:
                avg_pace = seconds_to_pace((valid['p_sec'] * valid['거리']).sum() / valid['거리'].sum())
        
        # 카드 시작
        st.markdown(f'<div class="member-card">', unsafe_allow_html=True)
        
        # 사진
        pic = m_data['사진'].dropna().iloc[0] if not m_data['사진'].dropna().empty else None
        if pic: st.markdown(f'<img src="{pic}" class="crew-photo">', unsafe_allow_html=True)
        else: st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
        
        # 이름 및 통계
        st.markdown(f'<div class="crew-name">{member}</div>', unsafe_allow_html=True)
        
        m_tw_dist = df[(df['러너']==member) & (df['날짜']>=tw_start.replace(hour=0,minute=0))]['거리'].sum()
        
        # 세로형에 최적화된 정보 나열
        st.markdown(f'''
            <div class="stat-row"><span class="stat-label">이번주 거리</span><span class="stat-value">{m_tw_dist:.2f}km</span></div>
            <div class="stat-row"><span class="stat-label">평균 페이스</span><span class="stat-value">{avg_pace}</span></div>
        ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
