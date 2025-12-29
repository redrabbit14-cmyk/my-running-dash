import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide")

# 2. 유틸리티 함수 (에러 방지용)
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
    try:
        if seconds is None or pd.isna(seconds) or seconds <= 0: return "N/A"
        return f"{int(seconds // 60)}:{int(seconds % 60):02d}"
    except: return "N/A"

# 3. 데이터 가져오기 (예외 처리 강화)
@st.cache_data(ttl=300) # 5분마다 갱신
def fetch_notion_data():
    try:
        response = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
            json={"page_size": 100}
        )
        if response.status_code != 200:
            st.error(f"노션 연결 실패: {response.status_code}")
            return pd.DataFrame()

        results = response.json().get("results", [])
        data = []
        for row in results:
            props = row.get("properties", {})
            
            # 필수 필드 체크 및 안전한 추출
            date_info = props.get("날짜", {}).get("date")
            if not date_info: continue
            
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            # 거리 추출 (여러 필드명 대응)
            dist_val = 0
            for f_name in ["실제 거리", "거리", "Distance"]:
                val = props.get(f_name, {}).get("number")
                if val is not None:
                    dist_val = val if val < 100 else val / 1000
                    break
            
            # 페이스 및 사진 추출
            mps = props.get("페이스", {}).get("number")
            
            photo_url = None
            files = props.get("사진", {}).get("files", [])
            if files:
                f_obj = files[0]
                photo_url = f_obj.get("file", {}).get("url") if f_obj.get("type") == "file" else f_obj.get("external", {}).get("url")

            data.append({
                "날짜": date_info.get("start")[:10],
                "러너": runner, "거리": dist_val, "페이스": mps_to_pace_str(mps),
                "사진": photo_url
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'])
            return df.sort_values('날짜', ascending=False)
        return df
    except Exception as e:
        st.warning(f"데이터 로드 중 일부 오류 발생: {e}")
        return pd.DataFrame()

# --- 화면 출력 ---
df = fetch_notion_data()
if df.empty:
    st.info("표시할 데이터가 없거나 노션 연결을 확인 중입니다.")
    st.stop()

st.title("🏃 러닝 크루 대시보드")

# 주간 요약 계산
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
this_week_start = today - timedelta(days=(today.weekday() + 1) % 7)
tw_df = df[df['날짜'] >= this_week_start]

st.metric("이번 주 크루 합산 거리", f"{tw_df['거리'].sum():.2f} km")

# 크루 카드 (Streamlit 기본 컬럼 사용 - 갤럭시 S25에서 세로로 보임)
crew_list = ["용남", "재탁", "주현", "유재"]
cols = st.columns(len(crew_list))

for i, member in enumerate(crew_list):
    with cols[i]:
        m_data = df[df['러너'] == member].head(7)
        
        # 가중 평균 페이스 계산
        avg_pace = "N/A"
        if not m_data.empty:
            m_data['p_sec'] = m_data['페이스'].apply(pace_to_seconds)
            valid = m_data.dropna(subset=['p_sec', '거리'])
            if not valid.empty and valid['거리'].sum() > 0:
                avg_pace = seconds_to_pace((valid['p_sec'] * valid['거리']).sum() / valid['거리'].sum())
        
        # 사진 출력 (데이터가 없을 경우 기본 아이콘)
        pic = m_data['사진'].dropna().iloc[0] if not m_data['사진'].dropna().empty else None
        if pic:
            st.image(pic, width=80)
        else:
            st.write("👤")
            
        st.subheader(member)
        st.write(f"페이스: {avg_pace}")
        st.write(f"이번주: {tw_df[tw_df['러너']==member]['거리'].sum():.1f}km")
