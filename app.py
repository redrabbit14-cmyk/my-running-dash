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
    
    return parse_notion_data(all_results)

def parse_notion_data(results):
    """노션 데이터 파싱"""
    records = []
    
    for idx, page in enumerate(results):
        props = page["properties"]
        
        try:
            # 1. 이름 (유형 없음 = Title)
            title_prop = props.get("이름", {}).get("title", [])
            name = title_prop[0].get("text", {}).get("content", "") if title_prop else f"Run-{idx}"
            
            # 2. 날짜 (유형 날짜)
            date_obj = props.get("날짜", {}).get("date", {})
            date_str = date_obj.get("start", "") if date_obj else ""
            
            # 3. 러너 (유형 선택) - select
            runner_obj = props.get("러너", {}).get("select", {})
            runner_name = runner_obj.get("name", "") if runner_obj else ""
            
            # 4. 실제 거리 (유형 수식)
            distance_prop = props.get("실제 거리", {})
            if distance_prop.get("type") == "formula":
                distance = distance_prop.get("formula", {}).get("number")
            else:
                distance = distance_prop.get("number")
            
            # 5. 페이스 (유형 숫자)
            pace = props.get("페이스", {}).get("number", 0)
            
            # 6. 거리 (유형 숫자)
            distance_manual = props.get("거리", {}).get("number", 0)
            
            # 7. 시간 (유형 텍스트)
            time_prop = props.get("시간", {}).get("rich_text", [])
            time_text = time_prop[0].get("text", {}).get("content", "0") if time_prop else "0"
            
            # 8. 고도 (유형 숫자)
            elevation = props.get("고도", {}).get("number", 0)
            
            # 10. 사진 (유형 파일과 미디어)
            files = props.get("사진", {}).get("files", [])
            photo_url = ""
            if files:
                file_obj = files[0]
                if file_obj.get("type") == "file":
                    photo_url = file_obj.get("file", {}).get("url", "")
                elif file_obj.get("type") == "external":
                    photo_url = file_obj.get("external", {}).get("url", "")
            
            # 실제 거리가 있고 날짜가 있으면 레코드 추가
            if date_str and distance:
                records.append({
                    "name": name,
                    "date": date_str,
                    "runner": runner_name,
                    "distance": distance,
                    "pace": pace if pace else 0,
                    "elevation": elevation if elevation else 0,
                    "time": time_text,
                    "photo_url": photo_url
                })
        except Exception as e:
            st.warning(f"파싱 에러 (항목 {idx}): {str(e)}")
            continue
    
    df = pd.DataFrame(records)
    
    if df.empty:
        return df
    
    # 날짜를 datetime으로 변환
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    
    # 중복 제거
    df = df.drop_duplicates(subset=["name", "date", "distance"], keep="first")
    
    return df.sort_values("date", ascending=False).reset_index(drop=True)

def get_week_range(date):
    """주어진 날짜가 속한 주의 월요일과 일요일 반환"""
    weekday = date.weekday()
    monday = date - timedelta(days=weekday)
    sunday = monday + timedelta(days=6)
    # 시간 정보를 00:00:00으로 설정하고 timezone 제거
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
    return monday, sunday

def filter_by_week(df, week_offset=0):
    """week_offset: 0=이번주, -1=지난주"""
    today = datetime.now()
    target_date = today + timedelta(weeks=week_offset)
    monday, sunday = get_week_range(target_date)
    
    # 이미 get_week_range에서 pd.Timestamp로 변환되어 있음
    return df[(df["date"] >= monday) & (df["date"] <= sunday)]

def main():
    st.title("🏃 러닝 크루 대시보드")
    
    # 데이터 로드
    with st.spinner("데이터를 불러오는 중..."):
        df = fetch_notion_data()
    
    if df.empty:
        st.warning("데이터가 없습니다.")
        return
    
    st.success(f"총 {len(df)}개의 러닝 기록을 불러왔습니다!")
    
    # 이번 주와 지난 주 데이터
    this_week_df = filter_by_week(df, 0)
    last_week_df = filter_by_week(df, -1)
    
    # ===== 상단: 크루 현황 =====
    st.header("📊 크루 현황")
    
    col1, col2, col3 = st.columns(3)
    
    # 이번 주 총 거리
    this_week_total = this_week_df["distance"].sum()
    
    # 지난 주 총 거리
    last_week_total = last_week_df["distance"].sum()
    
    # 전주 대비 증감률
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
    
    # ===== 중단: 크루 컨디션 =====
    st.header("💪 크루 컨디션")
    
    crew_members = ["재탁", "유재", "주현", "용남"]
    
    # 4개의 컬럼 생성
    cols = st.columns(4)
    
    for idx, member in enumerate(crew_members):
        with cols[idx]:
            # 해당 크루원의 전체 데이터에서 사진 가져오기
            member_all_data = df[df["runner"] == member]
            
            # 프로필 사진
            photo_url = None
            if not member_all_data.empty:
                # 가장 최근 데이터에서 사진 찾기
                for _, row in member_all_data.iterrows():
                    if row["photo_url"]:
                        photo_url = row["photo_url"]
                        break
            
            if photo_url:
                try:
                    response = requests.get(photo_url)
                    img = Image.open(BytesIO(response.content))
                    st.image(img, use_container_width=True)
                except Exception as e:
                    st.write(f"🏃 {member}")
                    st.caption("사진 로드 실패")
            else:
                st.write(f"🏃 {member}")
            
            st.markdown(f"### {member}")
            
            # 해당 크루원의 이번 주/지난 주 데이터
            member_this_week = this_week_df[this_week_df["runner"] == member]
            member_last_week = last_week_df[last_week_df["runner"] == member]
            
            # 이번 주 누계
            this_week_distance = member_this_week["distance"].sum()
            st.metric("이번 주", f"{this_week_distance:.1f} km")
            
            # 지난 주 누계
            last_week_distance = member_last_week["distance"].sum()
            st.metric("지난 주", f"{last_week_distance:.1f} km")
            
            # 최근 7일 평균 페이스
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_7days = df[(df["runner"] == member) & (df["date"] >= seven_days_ago)]
            
            if not recent_7days.empty and recent_7days["pace"].sum() > 0:
                avg_pace = recent_7days["pace"].mean()
                st.metric("평균 페이스", f"{avg_pace:.1f} 분/km")
            else:
                st.metric("평균 페이스", "기록 없음")
    
    st.divider()
    
    # ===== 하단: Insight & Fun =====
    st.header("🏆 Insight & Fun")
    
    # 디버깅: 이번 주 데이터 확인
    st.write(f"이번 주 데이터: {len(this_week_df)}개")
    
    if not this_week_df.empty:
        col1, col2, col3 = st.columns(3)
        
        # 1. 이 주의 마라토너 (가장 긴 거리)
        with col1:
            st.subheader("🏃 이 주의 마라토너")
            longest_run = this_week_df.loc[this_week_df["distance"].idxmax()]
            st.markdown(f"""
            **{longest_run['runner']}**  
            {longest_run['distance']:.2f} km  
            {longest_run['date'].strftime('%Y-%m-%d')}
            """)
        
        # 2. 이 주의 등산가 (가장 높은 고도)
        with col2:
            st.subheader("⛰️ 이 주의 등산가")
            highest_elevation = this_week_df.loc[this_week_df["elevation"].idxmax()]
            st.markdown(f"""
            **{highest_elevation['runner']}**  
            {highest_elevation['elevation']:.0f} m  
            {highest_elevation['date'].strftime('%Y-%m-%d')}
            """)
        
        # 3. 이 주의 폭주기관차 (가장 빠른 페이스)
        with col3:
            st.subheader("⚡ 이 주의 폭주기관차")
            # pace가 0보다 큰 것만 필터링
            valid_pace_df = this_week_df[this_week_df["pace"] > 0]
            if not valid_pace_df.empty:
                fastest_pace = valid_pace_df.loc[valid_pace_df["pace"].idxmin()]
                st.markdown(f"""
                **{fastest_pace['runner']}**  
                {fastest_pace['pace']:.2f} 분/km  
                {fastest_pace['date'].strftime('%Y-%m-%d')}
                """)
            else:
                st.info("페이스 기록이 없습니다.")
    else:
        st.info(f"이번 주 데이터가 없습니다. (이번 주: {get_week_range(datetime.now())[0].strftime('%Y-%m-%d')} ~ {get_week_range(datetime.now())[1].strftime('%Y-%m-%d')})")
    
    # 데이터 새로고침 버튼
    st.divider()
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
