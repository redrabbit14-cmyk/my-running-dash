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

# 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

# Notion API 헤더
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

@st.cache_data(ttl=3600)
def fetch_notion_data():
    """노션 데이터베이스에서 데이터 가져오기"""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    all_results = []
    has_more = True
    start_cursor = None
    
    while has_more:
        payload = {}
        if start_cursor:
            payload["start_cursor"] = start_cursor
            
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            st.error(f"노션 데이터 로드 실패: {response.status_code}")
            st.error(f"에러 메시지: {response.text}")
            return pd.DataFrame()
        
        data = response.json()
        all_results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    
    st.info(f"노션에서 {len(all_results)}개의 페이지를 가져왔습니다.")
    return parse_notion_data(all_results)

def parse_notion_data(results):
    """노션 데이터 파싱"""
    records = []
    
    st.write(f"파싱 시작: {len(results)}개 항목")
    
    for idx, page in enumerate(results):
        props = page["properties"]
        
        try:
            # 제목 (빈 문자열 컬럼) - 비어있을 수 있음
            title_prop = props.get("", {}).get("title", [])
            name = title_prop[0].get("text", {}).get("content", "") if title_prop else f"Run-{idx}"
            
            # 날짜
            date_obj = props.get("날짜", {}).get("date", {})
            date_str = date_obj.get("start", "") if date_obj else ""
            
            # 거리 (실제 거리) - formula 타입
            distance_prop = props.get("실제 거리", {})
            if distance_prop.get("type") == "formula":
                distance = distance_prop.get("formula", {}).get("number")
            else:
                distance = distance_prop.get("number")
            
            # 페이스
            pace_prop = props.get("페이스", {}).get("rich_text", [])
            pace_text = pace_prop[0].get("text", {}).get("content", "0") if pace_prop else "0"
            
            # 고도
            elevation_prop = props.get("고도", {})
            if elevation_prop.get("type") == "formula":
                elevation = elevation_prop.get("formula", {}).get("number", 0)
            else:
                elevation = elevation_prop.get("number", 0)
            
            # 시간 (runners)
            time_prop = props.get("runners", {}).get("rich_text", [])
            time_text = time_prop[0].get("text", {}).get("content", "0") if time_prop else "0"
            
            # 사람
            people = props.get("사람", {}).get("people", [])
            person_name = people[0].get("name", "") if people else ""
            person_avatar = people[0].get("avatar_url", "") if people else ""
            
            # name 조건 제거, date와 distance만 확인
            if date_str and distance:
                records.append({
                    "name": name,
                    "date": date_str,
                    "distance": distance,
                    "pace": pace_text,
                    "elevation": elevation if elevation else 0,
                    "time": float(time_text) if time_text else 0,
                    "person_name": person_name,
                    "person_avatar": person_avatar
                })
        except Exception as e:
            st.warning(f"파싱 에러 (항목 {idx}): {str(e)}")
            continue
    
    st.write(f"파싱 완료: {len(records)}개 레코드")
    
    df = pd.DataFrame(records)
    
    if df.empty:
        st.error("DataFrame이 비어있습니다!")
        return df
    
    df["date"] = pd.to_datetime(df["date"])
    
    df = df.drop_duplicates(subset=["name", "date", "distance"], keep="first")
    
    df["pace_numeric"] = df["pace"].apply(lambda x: float(str(x).replace(",", "")) if x else 0)
    
    st.success(f"최종 데이터: {len(df)}개 레코드")
    
    return df.sort_values("date", ascending=False).reset_index(drop=True)

def get_week_range(date):
    """주어진 날짜가 속한 주의 월요일과 일요일 반환"""
    weekday = date.weekday()
    monday = date - timedelta(days=weekday)
    sunday = monday + timedelta(days=6)
    return monday, sunday

def filter_by_week(df, week_offset=0):
    """week_offset: 0=이번주, -1=지난주"""
    today = datetime.now()
    target_date = today + timedelta(weeks=week_offset)
    monday, sunday = get_week_range(target_date)
    
    return df[(df["date"] >= monday) & (df["date"] <= sunday)]

def main():
    st.title("🏃 러닝 크루 대시보드")
    
    with st.spinner("데이터를 불러오는 중..."):
        df = fetch_notion_data()
    
    if df.empty:
        st.warning("데이터가 없습니다.")
        return
    
    this_week_df = filter_by_week(df, 0)
    last_week_df = filter_by_week(df, -1)
    
    st.header("📊 크루 현황")
    
    col1, col2, col3 = st.columns(3)
    
    this_week_total = this_week_df["distance"].sum()
    last_week_total = last_week_df["distance"].sum()
    
    if last_week_total > 0:
        change_pct = ((this_week_total - last_week_total) / last_week_total) * 100
    else:
        change_pct = 0
    
    with col1:
        st.metric("이번 주 총 거리", f"{this_week_total:.1f} km")
    
    with col2:
        st.metric("지난 주 총 거리", f"{last_week_total:.1f} km")
    
    with col3:
        st.metric("전주 대비", f"{change_pct:+.1f}%", delta=f"{this_week_total - last_week_total:.1f} km")
    
    st.divider()
    
    st.header("💪 크루 컨디션")
    
    crew_members = ["재탁", "유재", "주현", "용남"]
    
    cols = st.columns(4)
    
    for idx, member in enumerate(crew_members):
        with cols[idx]:
            member_this_week = this_week_df[this_week_df["person_name"] == member]
            member_last_week = last_week_df[last_week_df["person_name"] == member]
            
            if not member_this_week.empty and member_this_week.iloc[0]["person_avatar"]:
                try:
                    avatar_url = member_this_week.iloc[0]["person_avatar"]
                    response = requests.get(avatar_url)
                    img = Image.open(BytesIO(response.content))
                    st.image(img, use_container_width=True)
                except:
                    st.image("https://via.placeholder.com/150", use_container_width=True)
            else:
                st.image("https://via.placeholder.com/150", use_container_width=True)
            
            st.markdown(f"### {member}")
            
            this_week_distance = member_this_week["distance"].sum()
            st.metric("이번 주", f"{this_week_distance:.1f} km")
            
            last_week_distance = member_last_week["distance"].sum()
            st.metric("지난 주", f"{last_week_distance:.1f} km")
            
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_7days = df[(df["person_name"] == member) & (df["date"] >= seven_days_ago)]
            
            if not recent_7days.empty and recent_7days["pace_numeric"].sum() > 0:
                avg_pace = recent_7days["pace_numeric"].mean()
                st.metric("평균 페이스", f"{avg_pace:.1f} 분/km")
            else:
                st.metric("평균 페이스", "기록 없음")
    
    st.divider()
    
    st.header("🏆 Insight & Fun")
    
    if not this_week_df.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("🏃 이 주의 마라토너")
            longest_run = this_week_df.loc[this_week_df["distance"].idxmax()]
            st.markdown(f"""
            **{longest_run['person_name']}**  
            {longest_run['distance']:.2f} km  
            {longest_run['date'].strftime('%Y-%m-%d')}
            """)
        
        with col2:
            st.subheader("⛰️ 이 주의 등산가")
            highest_elevation = this_week_df.loc[this_week_df["elevation"].idxmax()]
            st.markdown(f"""
            **{highest_elevation['person_name']}**  
            {highest_elevation['elevation']:.0f} m  
            {highest_elevation['date'].strftime('%Y-%m-%d')}
            """)
        
        with col3:
            st.subheader("⚡ 이 주의 폭주기관차")
            valid_pace_df = this_week_df[this_week_df["pace_numeric"] > 0]
            if not valid_pace_df.empty:
                fastest_pace = valid_pace_df.loc[valid_pace_df["pace_numeric"].idxmin()]
                st.markdown(f"""
                **{fastest_pace['person_name']}**  
                {fastest_pace['pace_numeric']:.2f} 분/km  
                {fastest_pace['date'].strftime('%Y-%m-%d')}
                """)
            else:
                st.info("페이스 기록이 없습니다.")
    else:
        st.info("이번 주 데이터가 없습니다.")
    
    st.divider()
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
