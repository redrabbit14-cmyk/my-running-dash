import streamlit as st
import pandas as pd
import requests

# 1. 페이지 설정
st.set_page_config(page_title="Running Crew Dashboard", layout="wide")

# 2. 보안 설정 (Secrets 확인)
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID")
WEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY")

st.title("🏃‍♂️ 러닝 크루 주간 활동 리포트")

# 3. 날씨 섹션 (OpenWeather API)
st.subheader("📅 주간 날씨 (부산)")
if WEATHER_API_KEY:
    try:
        # 부산 해운대/영도 인근 날씨 데이터 가져오기
        w_url = f"https://api.openweathermap.org/data/2.5/weather?q=Busan&appid={WEATHER_API_KEY}&units=metric"
        res = requests.get(w_url).json()
        temp = res["main"]["temp"]
        weather_main = res["weather"][0]["main"]
        st.metric(label="현재 부산 기온", value=f"{temp} °C", delta=weather_main)
    except:
        st.info("날씨 데이터를 불러오는 중입니다.")
else:
    st.warning("날씨 API 키가 설정되지 않았습니다.")

st.divider()

# 4. 크루 컨디션 섹션
st.subheader("👥 크루 컨디션")

# 노션 연동 시도 (토큰이 있을 때만)
if NOTION_TOKEN and DATABASE_ID:
    st.info("🔗 노션 데이터베이스 연결을 시도합니다.")
    # 실제 노션 파싱 로직은 데이터 구조에 따라 다르므로 우선 샘플 데이터를 보여줍니다.
else:
    st.write("💡 노션 연결 전입니다. 샘플 데이터를 표시합니다.")

# 기획안 기반 샘플 데이터
crew_df = pd.DataFrame({
    "이름": ["용남", "주현", "유재", "재탁"],
    "주간거리": ["45.2 km", "38.5 km", "20.0 km", "15.3 km"],
    "전주대비": ["+12%", "-5%", "+20%", "0%"],
    "평균속도": ["5:30/km", "5:45/km", "6:10/km", "6:30/km"],
    "연속휴식": ["1일", "3일", "0일", "5일"]
})
st.table(crew_df)

# 5. Insight & Fun
st.divider()
st.subheader("🏆 Insight & Fun")
col1, col2, col3 = st.columns(3)
col1.info("**가장 긴 거리**\n\n용남 / 21km / 12-24")
col2.success("**가장 높은 고도**\n\n주현 / 150m / 12-25")
col3.warning("**가장 빠른 속도**\n\n유재 / 4:50/km / 12-26")

# 6. AI 코치 추천
st.divider()
st.subheader("🤖 AI 코치 훈련 추천")
if st.button("추천받기"):
    st.balloons()
    st.success("✅ **마라토너 용남님을 위한 추천:** 오늘은 복직 전 체력 관리를 위해 영도 해안산책로에서 10km 빌드업 주를 추천합니다!")
