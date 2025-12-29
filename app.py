import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일
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
    """스트라바 m/s 숫자를 '분:초' 문자열로 변환"""
    try:
        if mps is None or mps <= 0:
            return "N/A"
        total_seconds = 1000 / mps
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        return f"{minutes}:{seconds:02d}"
    except:
        return "N/A"

def pace_to_seconds(pace_str):
    """'분:초' 페이스 문자열을 계산용 초 단위로 변환"""
    try:
        if not pace_str or pd.isna(pace_str) or pace_str == "N/A":
            return None
        pace_str = str(pace_str).strip().replace("'", ":").replace('"', "").replace("’", ":").replace("´", ":")
        parts = pace_str.split(':')
        return int(float(parts[0]) * 60 + float(parts[1]))
    except:
        return None

def seconds_to_pace(seconds):
    """계산된 평균 초 단위를 다시 '분:초' 문자열로 변환"""
    if seconds is None or pd.isna(seconds) or seconds <= 0:
        return "N/A"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"

@st.cache_data(ttl=300)
def fetch_notion_data():
    """노션 데이터베이스에서 데이터 가져오기"""
    try:
        response = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            json={"page_size": 100}
        )
        
        data = []
        for row in response.json().get("results", []):
            props = row.get("properties", {})
            date_obj = props.get("날짜", {}).get("date", {})
            if not date_obj: continue
            
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            distance = 0
            for field in ["실제 거리", "거리", "Distance"]:
                val = props.get(field, {}).get("number")
                if val is not None:
                    distance = val if val < 100 else val / 1000
                    break
            
            mps_val = props.get("페이스", {}).get("number")
            pace = mps_to_pace_str(mps_val)
            
            elevation = props.get("고도", {}).get("number", 0) or 0
            
            photo_url = None
            files = props.get("사진", {}).get("files", [])
            if files:
                f = files[0]
                photo_url = f.get("file", {}).get("url") if f.get("type") == "file" else f.get("external", {}).get("url")

            data.append({
                "날짜": date_obj.get("start")[:10],
                "러너": runner,
                "거리": distance,
                "페이스": pace,
                "고도": elevation,
                "사진": photo_url,
                "생성시간": row.get("created_time", "")
            })
        
        df = pd.DataFrame(data)
        df['날짜'] = pd.to_datetime(df['날짜'])
        df = df.sort_values(['날짜', '생성시간'], ascending=[False, False])
        return df[df['거리'] > 0]
    except Exception as e:
        st.error(f"데이터 로딩 오류: {e}")
        return pd.DataFrame()

# --- 메인 실행 ---
df = fetch_notion_data()
if df.empty:
    st.warning("⚠️ 데이터를 불러올 수 없습니다.")
    st.stop()

st.title("🏃 러닝 크루 대시보드")

# 주간 기준
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
this_week_start = today - timedelta(days=(today.weekday() + 1) % 7)
last_week_start = this_week_start - timedelta(days=7)

tw = df[df['날짜'] >= this_week_start]
lw = df[(df['날짜'] >= last_week_start) & (df['날짜'] < this_week_start)]

# 1. 총거리 카드
st.markdown(f'''
    <div class="section-card">
        <div class="total-distance-card">
            <div style="font-size:16px; color:#047857; font-weight:600; margin-bottom:5px;">총거리 (크루 합산)</div>
            <div style="font-size:48px;font-weight:800;color:#047857;">{tw['거리'].sum():.2f} km</div>
            <div style="font-size:14px;color:#6b7280;">이번 주 | 지난주 전체: {lw['거리'].sum():.1f} km</div>
        </div>
    </div>
''', unsafe_allow_html=True)

# 2. 크루 컨디션
st.markdown('<div class="section-card"><div style="font-size:18px; font-weight:700; margin-bottom:15px;">👥 크루 컨디션 (최근 7회 기록 기반)</div>', unsafe_allow_html=True)
crew_list = ["용남", "재탁", "주현", "유재"]
cols = st.columns(4)

for idx, member in enumerate(crew_list):
    with cols[idx]:
        m_all = df[df['러너'] == member].head(7) # 최근 7개 기록
        
        # 가중 평균 페이스 계산 로직 [핵심 수정 부분]
        if not m_all.empty:
            m_all['페이스_초'] = m_all['페이스'].apply(pace_to_seconds)
            valid_data = m_all.dropna(subset=['페이스_초', '거리'])
            
            if not valid_data.empty:
                # (페이스(초/km) * 거리)의 합 = 총 소요 시간
                total_seconds = (valid_data['페이스_초'] * valid_data['거리']).sum()
                total_dist = valid_data['거리'].sum()
                avg_pace_str = seconds_to_pace(total_seconds / total_dist)
            else:
                avg_pace_str = "N/A"
        else:
            avg_pace_str = "N/A"

        # 기존 UI 요소 (거리, 증감, 휴식일 등)
        tw_dist = tw[tw['러너'] == member]['거리'].sum()
        lw_dist = lw[lw['러너'] == member]['거리'].sum()
        change = ((tw_dist - lw_dist) / lw_dist * 100) if lw_dist > 0 else (100 if tw_dist > 0 else 0)
        
        photo = m_all['사진'].dropna().iloc[0] if not m_all['사진'].dropna().empty else None
        if photo: st.markdown(f'<img src="{photo}" class="crew-photo">', unsafe_allow_html=True)
        else: st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
        
        st.markdown(f'<div style="text-align:center; font-weight:700; margin-bottom:10px;">{member}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="crew-stat-box" style="background:#f0f9ff;"><div class="stat-label">이번주 / 지난주</div><div class="stat-value">{tw_dist:.2f} / {lw_dist:.1f}km</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="crew-stat-box" style="background:#f0fdf4;"><div class="stat-label">전주 대비</div><div class="stat-value">{change:+.1f}%</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="crew-stat-box" style="background:#f5f3ff;"><div class="stat-label">평균 페이스(가중)</div><div class="stat-value">{avg_pace_str}</div></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
