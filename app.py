import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# 1. 보안 설정 (Secrets에서 토큰 및 키 가져오기)
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DATABASE_ID = st.secrets["DATABASE_ID"]
    WEATHER_API_KEY = st.secrets["OPENWEATHER_API_KEY"]
except Exception:
    st.error("Secrets 설정이 필요합니다. GitHub의 Settings > Secrets에 키를 등록하거나 .streamlit/secrets.toml 파일을 확인하세요.")
    st.stop()

# --- 노션 데이터 가져오기 함수 ---
def get_notion_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers)
    if response.status_status == 200:
        data = response.json()
        # 여기서 노션 데이터 구조에 맞게 파싱(Parsing) 로직이 추가되어야 합니다.
        # 일단은 성공 메시지만 띄웁니다.
        return data
    else:
        st.error(f"노션 연결 실패: {response.status_code}")
        return None

# --- 날씨 데이터 가져오기 함수 (부산 해운대/영도 기준) ---
def get_weather():
    # 부산 위경도 기준 (해운대/영도 인근)
    url = f"https://api.openweathermap.org/data/2.5/weather?q=Busan&appid={WEATHER_API_KEY}&units=metric"
    res = requests.get(url).json()
    return res

# --- UI 렌더링 ---
st.set_page_config(page_title="러닝 크루 대시보드", layout="wide")
st.title("🏃‍♂️ 크루 러닝 리포트 (Notion 연동)")

# 2. 날씨 섹션 (실제 API 데이터 반영)
weather_data = get_weather()
st.subheader("🌦️ 실시간 부산 날씨")
if weather_data.get("main"):
    temp = weather_data["main"]["temp"]
    weather_desc = weather_data["weather"][0]["main"]
    st.metric(label="현재 부산 온도", value=f"{temp} °C", delta=weather_desc)

st.divider()

# 3. 크루 데이터 (노션 연동)
st.subheader("📊 노션 연동 크루 컨디션")
notion_raw_data = get_notion_data()

if notion_raw_data:
    st.success("✅ 노션에서 '노선표' 데이터를 성공적으로 불러왔습니다!")
    # 실제 구현 시에는 notion_raw_data를 DataFrame으로 변환하는 코드가 들어갑니다.
    # 예시: st.write(notion_raw_data) 
else:
    st.warning("노션 데이터를 불러오는 중입니다...")

# 4. AI 코치 섹션 (기존 기획 유지)
st.divider()
st.subheader("🤖 AI 코치 훈련 추천")
if st.button("추천받기"):
    st.info("오늘의 추천: 노션에 기록된 마지막 훈련일로부터 2일이 지났습니다. 영도 해안산책로 코스 10km를 권장합니다!")
