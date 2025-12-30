import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
from PIL import Image
from io import BytesIO

# 페이지 설정
st.set_page_config(
    page_title="러닝 크루 대시보드",
    page_icon="🏃",
    layout="wide"
)

# CSS: 사진 크기 고정 및 레이아웃 최적화 (스크롤 방지)
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; }
    .stImage > img { border-radius: 10px; object-fit: cover; height: 160px !important; }
    div[data-testid="stVerticalBlock"] > div:has(div.stImage) { text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def time_to_seconds(time_str):
    """'MM:SS' 또는 'HH:MM:SS' 문자열을 초로 변환"""
    try:
        parts = list(map(int, str(time_str).split(':')))
        if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2: return parts[0]*60 + parts[1]
        return 0
    except: return 0

@st.cache_data(ttl=3600)
def fetch_notion_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    all_results = []
    has_more, start_cursor = True, None
    
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
            runner_name = props.get("러너", {}).get("select", {}).get("name", "")
            date_obj = props.get("날짜", {}).get("date", {})
            date_str = date_obj.get("start", "") if date_obj else ""
            
            dist_prop = props.get("실제 거리", {})
            distance = dist_prop.get("formula", {}).get("number") if dist_prop.get("type") == "formula" else dist_prop.get("number")
            
            time_prop = props.get("시간", {}).get("rich_text", [])
            time_text = time_prop[0].get("text", {}).get("content", "0") if time_prop else "0"
            
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
                    "duration_sec": time_to_seconds(time_text),
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
        st.warning("데이터가 없습니다.")
        return

    # 주간 범위 설정 (에러 수정됨: hours, minutes 사용)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6, hours=23, minutes=59)
    this_week_df = df[(df["date"] >= mon) & (df["date"] <= sun)]

    st.header("💪 크루 컨디션")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        with cols[idx]:
            m_data = df[df["runner"] == member]
            
            # 사진 표시 (URL 만료 대비 처리)
            photo_url = None
            if not m_data.empty:
                valid_photos = m_data[m_data['photo_url'] != ""]
                if not valid_photos.empty:
                    photo_url = valid_photos.iloc[0]['photo_url']
            
            if photo_url:
                st.image(photo_url, use_container_width=True)
            else:
                st.info(f"👤 {member}")

            st.markdown(f"### {member}")
            
            # 기록 계산
            m_this_week = this_week_df[this_week_df["runner"] == member]
            st.metric("이번 주 거리", f"{m_this_week['distance'].sum():.1f} km")

            # 7일 평균 페이스 (정확한 가중 평균 방식)
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_7d = m_data[m_data["date"] >= seven_days_ago]
            
            if not recent_7d.empty and recent_7d["distance"].sum() > 0:
                avg_pace_sec = recent_7d["duration_sec"].sum() / recent_7d["distance"].sum()
                st.metric("7일 평균 페이스", f"{int(avg_pace_sec // 60)}'{int(avg_pace_sec % 60)}\"")
            else:
                st.metric("7일 평균 페이스", "-")

    st.divider()
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
