import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일 (기존 스타일 유지)
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
        if not pace_str or pace_str == "N/A": return None
        parts = str(pace_str).split(':')
        return int(float(parts[0]) * 60 + float(parts[1]))
    except: return None

def seconds_to_pace(seconds):
    if seconds is None or seconds <= 0: return "N/A"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"

# 사진 링크 만료 대응을 위해 캐시 시간을 1시간(3600초) 이내로 설정 권장
@st.cache_data(ttl=600) 
def fetch_notion_data():
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
            
            # 거리 추출
            distance = 0
            for field in ["실제 거리", "거리", "Distance"]:
                val = props.get(field, {}).get("number")
                if val is not None:
                    distance = val if val < 100 else val / 1000
                    break
            
            # 페이스(m/s) 추출 및 변환
            mps_val = props.get("페이스", {}).get("number")
            pace = mps_to_pace_str(mps_val)
            
            # 고도 추출
            elevation = props.get("고도", {}).get("number", 0) or 0
            
            # 사진 URL 추출 (노션 내부 파일 호스팅 대응)
            photo_url = None
            files = props.get("사진", {}).get("files", [])
            if files:
                f_obj = files[0]
                # 노션에 직접 업로드한 파일은 'file' 타입이며 임시 URL을 제공함
                if f_obj.get("type") == "file":
                    photo_url = f_obj.get("file", {}).get("url")
                elif f_obj.get("type") == "external":
                    photo_url = f_obj.get("external", {}).get("url")

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
        return df.sort_values(['날짜', '생성시간'], ascending=[False, False])
    except Exception as e:
        st.error(f"데이터 로딩 오류: {e}")
        return pd.DataFrame()

# --- 실행 ---
df = fetch_notion_data()
if df.empty: st.stop()

st.title("🏃 러닝 크루 대시보드")

# 시간 기준 설정
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
this_week_start = today - timedelta(days=(today.weekday() + 1) % 7)

# 1. 크루 컨디션 섹션
st.markdown('<div class="section-card"><div style="font-size:18px; font-weight:700; margin-bottom:15px;">👥 크루 컨디션 (최근 7회 가중 평균)</div>', unsafe_allow_html=True)
crew_list = ["용남", "재탁", "주현", "유재"]
cols = st.columns(4)

for idx, member in enumerate(crew_list):
    with cols[idx]:
        m_all = df[df['러너'] == member].head(7)
        
        # 가중 평균 페이스 계산
        avg_pace_str = "N/A"
        if not m_all.empty:
            m_all['페이스_초'] = m_all['페이스'].apply(pace_to_seconds)
            valid = m_all.dropna(subset=['페이스_초', '거리'])
            if not valid.empty and valid['거리'].sum() > 0:
                avg_pace_str = seconds_to_pace((valid['페이스_초'] * valid['거리']).sum() / valid['거리'].sum())

        # 사진 표시 (URL이 존재할 때만 표시)
        photo = None
        valid_photos = m_all['사진'].dropna()
        if not valid_photos.empty:
            photo = valid_photos.iloc[0]
        
        if photo:
            st.markdown(f'<img src="{photo}" class="crew-photo">', unsafe_allow_html=True)
        else:
            st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
        
        # 통계 출력 (거리/증감/페이스)
        st.markdown(f'<div style="text-align:center; font-weight:700; margin-bottom:10px;">{member}</div>', unsafe_allow_html=True)
        # (기존 거리 및 증감 로직 코드는 이전과 동일하게 유지...)
        st.markdown(f'<div class="crew-stat-box" style="background:#f5f3ff;"><div class="stat-label">평균 페이스(가중)</div><div class="stat-value">{avg_pace_str}</div></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
