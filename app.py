import streamlit as st
import pandas as pd
import requests

# 1. 보안 설정 (Secrets에서 키 가져오기)
# Streamlit Cloud의 Settings > Secrets에 반드시 키를 등록해야 에러가 안 납니다.
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DATABASE_ID = st.secrets["DATABASE_ID"]
    WEATHER_API_KEY = st.secrets["OPENWEATHER_API_KEY"]
except Exception:
    st.warning("⚠️ API 키 설정(Secrets)이 완료되지 않았습니다. 기본 화면을 먼저 보여드립니다.")
    NOTION_TOKEN = DATABASE_ID = WEATHER_API_KEY = None

# 2. UI 레이아웃
st.set_page_config(page_title="러닝 크루 대시보드", layout="wide")
st.title("🏃‍♂️ 크루 러닝 리포트")

# --- 날씨 섹션 ---
st.subheader("🌦️ 주간 날씨 (부산)")
if WEATHER_API_KEY:
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q=Busan&appid={WEATHER_API_KEY}&units=metric"
        res = requests.get(url).json()
        temp = res["main"]["temp"]
        st.metric("현재 온도", f"{temp} °C")
    except:
        st.write("날씨 데이터를 불러올 수 없습니다.")
else:
    st.write("날씨 API 키를 등록해주세요.")

st.divider()

# --- 크루 데이터 섹션 ---
st.subheader("📊 크루 컨디션")

# 노션 연동 전, 기획안 형태를 보여주기 위한 샘플 데이터
sample_df = pd.DataFrame({
    "이름": ["용남", "주현", "유재", "재탁"],
    "주간거리(km)": [45.2, 38.5, 20.0, 15.3],
    "평균속도": ["5:30", "5:45", "6:10", "6:30"],
    "연속휴식": [1, 3, 0, 5]
})
st.table(sample_df)

# --- AI 코치 추천 ---
st.divider()
st.subheader("🤖 AI 코치 훈련 추천")
if st.button("추천받기"):
    st.success("✅ 오늘은 해운대 해변로에서 가벼운 회복주 5km를 추천합니다!")
