import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
from PIL import Image
from io import BytesIO

# 1. 페이지 설정
st.set_page_config(
    page_title="러닝 크루 대시보드",
    page_icon="🏃",
    layout="wide"
)

# 2. CSS: 사진 크기 적정화 및 텍스트 정렬
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    .stImage > img { 
        border-radius: 15px; 
        object-fit: cover; 
        height: 200px !important; /* 사진 높이를 200px로 조절하여 한 화면에 들어오게 함 */
    }
    h3 { margin-bottom: 0px; padding-bottom: 5px; }
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
            runner_name = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            date_obj = props.get("날짜", {}).get("date", {})
            date_str = date_obj.get("start", "") if date_obj else ""
            dist_prop = props.get("실제 거리", {})
            distance = dist_prop.get("formula", {}).get("number") if dist_prop.get("type") == "formula" else dist_prop.get("number")
            time_prop = props.get("시간", {}).get("rich_text", [])
            time_text = time_prop[0].get("text", {}).get("content", "0") if time_prop else "0"
            elevation = props.get("고도", {}).get("number", 0) or 0
            files = props.get("사진", {}).get("files", [])
            photo_url = ""
            if files:
                f = files[0]
                photo_url = f.get("file", {}).get("url") if f.get("type") == "file" else f.get("external", {}).get("url")

            if date_str and distance:
                records.append({
                    "date": date_str, "runner": runner_name, "distance": float(distance),
                    "duration_sec": time_to_seconds(time_text), "elevation": elevation, "photo_url": photo_url
                })
        except: continue
    df = pd.DataFrame(records)
    if not df.empty: df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = fetch_notion_data()
    if df.empty:
        st.warning("노션에서 데이터를 가져오지 못했습니다.")
        return

    # 주간 데이터 필터링 (월요일 시작 기준)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6, hours=23, minutes=59)
    last_mon = mon - timedelta(days=7)
    last_sun = mon - timedelta(seconds=1)

    this_week_df = df[(df["date"] >= mon) & (df["date"] <= sun)]
    last_week_df = df[(df["date"] >= last_mon) & (df["date"] <= last_sun)]

    # --- 1. 크루 현황 섹션 ---
    st.header("📊 크루 현황")
    c1, c2, c3 = st.columns(3)
    tw_total = this_week_df["distance"].sum()
    lw_total = last_week_df["distance"].sum()
    diff = tw_total - lw_total
    c1.metric("이번 주 총 거리", f"{tw_total:.1f} km")
    c2.metric("지난 주 총 거리", f"{lw_total:.1f} km")
    c3.metric("전주 대비", f"{tw_total-lw_total:+.1f} km", delta=f"{((tw_total-lw_total)/lw_total*100 if lw_total>0 else 0):.1f}%")

    st.divider()

    # --- 2. 크루 컨디션 섹션 ---
    st.header("💪 크루 컨디션")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        with cols[idx]:
            m_data = df[df["runner"] == member]
            photo_url = m_data[m_data['photo_url'] != ""].iloc[0]['photo_url'] if not m_data[m_data['photo_url'] != ""].empty else None
            
            if photo_url: st.image(photo_url, use_container_width=True)
            else: st.info(f"👤 {member}")
            
            st.subheader(member)
            dist = this_week_df[this_week_df["runner"] == member]["distance"].sum()
            st.metric("주간 거리", f"{dist:.1f} km")

            recent_7d = m_data[m_data["date"] >= (datetime.now() - timedelta(days=7))]
            if not recent_7d.empty and recent_7d["distance"].sum() > 0:
                sec = recent_7d["duration_sec"].sum() / recent_7d["distance"].sum()
                st.metric("7일 평균 페이스", f"{int(sec//60)}'{int(sec%60)}\"")
            else: st.metric("7일 평균 페이스", "-")

    st.divider()

    # --- 3. Insight & Fun 섹션 ---
    st.header("🏆 Insight & Fun")
    if not this_week_df.empty:
        i1, i2, i3 = st.columns(3)
        with i1:
            best_dist = this_week_df.loc[this_week_df["distance"].idxmax()]
            st.subheader("🏃 이 주의 마라토너")
            st.success(f"{best_dist['runner']} ({best_dist['distance']:.1f}km)")
        with i2:
            best_elev = this_week_df.loc[this_week_df["elevation"].idxmax()]
            st.subheader("⛰️ 이 주의 등산가")
            st.warning(f"{best_elev['runner']} ({best_elev['elevation']}m)")
        with i3:
            this_week_df['pace_val'] = this_week_df['duration_sec'] / this_week_df['distance']
            best_pace = this_week_df[this_week_df['pace_val'] > 0].loc[this_week_df['pace_val'].idxmin()]
            st.subheader("⚡ 이 주의 폭주기관차")
            st.info(f"{best_pace['runner']} ({int(best_pace['pace_val']//60)}'{int(best_pace['pace_val']%60)}\")")
    else:
        st.info("이번 주 활동 데이터가 아직 없습니다. 힘내서 달려볼까요?")

    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
