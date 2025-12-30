import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
from PIL import Image
from io import BytesIO

# 페이지 설정: 와이드 모드 유지
st.set_page_config(
    page_title="러닝 크루 대시보드",
    page_icon="🏃",
    layout="wide"
)

# [수정] CSS 추가: 사진 크기 고정 및 스크롤 최소화
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .stImage > img { border-radius: 10px; object-fit: cover; height: 150px !important; }
    </style>
    """, unsafe_allow_html=True)

# 환경 설정 (st.secrets 사용 권장)
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def time_to_seconds(time_str):
    """'MM:SS' 또는 'HH:MM:SS' 형태의 문자열을 초로 변환"""
    try:
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2: return parts[0]*60 + parts[1]
        return 0
    except: return 0

@st.cache_data(ttl=3600) # 1시간마다 갱신 (노션 URL 만료 대비)
def fetch_notion_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    all_results = []
    has_more = True
    start_cursor = None
    
    while has_more:
        payload = {"start_cursor": start_cursor} if start_cursor else {}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200: return pd.DataFrame()
        
        data = response.json()
        all_results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    
    return parse_notion_data(all_results)

def parse_notion_data(results):
    records = []
    for page in results:
        props = page["properties"]
        try:
            # 1. 이름 & 러너
            runner_name = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            # 2. 날짜
            date_obj = props.get("날짜", {}).get("date", {})
            date_str = date_obj.get("start", "") if date_obj else ""
            
            # 3. 거리 (수식 또는 숫자)
            dist_prop = props.get("실제 거리", {})
            distance = dist_prop.get("formula", {}).get("number") if dist_prop.get("type") == "formula" else dist_prop.get("number")
            
            # 4. 시간 (페이스 계산용)
            time_prop = props.get("시간", {}).get("rich_text", [])
            time_text = time_prop[0].get("text", {}).get("content", "0") if time_prop else "0"
            duration_sec = time_to_seconds(time_text)
            
            # 5. 사진 URL (유형 체크)
            files = props.get("사진", {}).get("files", [])
            photo_url = ""
            if files:
                f = files[0]
                photo_url = f.get("file", {}).get("url") if f.get("type") == "file" else f.get("external", {}).get("url")

            if date_str and distance:
                records.append({
                    "date": date_str,
                    "runner": runner_name,
                    "distance": float(distance),
                    "duration_sec": duration_sec,
                    "elevation": props.get("고도", {}).get("number", 0) or 0,
                    "photo_url": photo_url
                })
        except: continue
    
    df = pd.DataFrame(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = fetch_notion_data()
    
    if df.empty:
        st.warning("데이터를 불러오지 못했습니다. 노션 설정을 확인하세요.")
        return

    # 주간 데이터 필터링
    today = datetime.now()
    mon = (today - timedelta(days=today.weekday())).replace(hour=0,minute=0,second=0)
    sun = mon + timedelta(days=6, hour=23, minute=59)
    this_week_df = df[(df["date"] >= mon) & (df["date"] <= sun)]

    # --- 중단: 크루 컨디션 (수정 포인트) ---
    st.header("💪 크루 컨디션")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        with cols[idx]:
            m_data = df[df["runner"] == member]
            
            # 사진 표시 로직 보강
            photo_shown = False
            if not m_data.empty:
                latest_photo = m_data.dropna(subset=['photo_url']).iloc[0]['photo_url'] if 'photo_url' in m_data.columns else None
                if latest_photo:
                    try:
                        # [중요] 노션 URL 만료 이슈 해결을 위해 캐싱 활용 가능
                        st.image(latest_photo, use_container_width=True)
                        photo_shown = True
                    except: pass
            
            if not photo_shown:
                st.info(f"👤 {member}") # 사진 없을 시 대체 아이콘

            st.subheader(member)
            
            # 이번 주 거리
            m_this_week = this_week_df[this_week_df["runner"] == member]
            dist_val = m_this_week["distance"].sum()
            st.metric("이번 주", f"{dist_val:.1f} km")

            # [해결 3] 최근 7일 평균 페이스 계산 수정
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_7d = m_data[m_data["date"] >= shadow_days_ago]
            
            if not recent_7d.empty and recent_7d["distance"].sum() > 0:
                total_dist = recent_7d["distance"].sum()
                total_sec = recent_7d["duration_sec"].sum()
                # 페이스 계산: 초/km -> MM:SS 변환
                avg_pace_sec = total_sec / total_dist
                minutes = int(avg_pace_sec // 60)
                seconds = int(avg_pace_sec % 60)
                st.metric("7일 평균 페이스", f"{minutes}'{seconds}\"")
            else:
                st.metric("7일 평균 페이스", "-")

    # --- 하단: Insight & 데이터 새로고침 ---
    if st.button("🔄 데이터 새로고침 (사진이 안 나올 때 클릭)"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
