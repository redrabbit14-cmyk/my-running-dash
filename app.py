import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# =========================
# 환경 변수 (Streamlit Cloud 대응)
# =========================
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN", os.environ.get("NOTION_TOKEN"))
DATABASE_ID = st.secrets.get("DATABASE_ID", os.environ.get("DATABASE_ID"))
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", os.environ.get("OPENWEATHER_API_KEY"))

st.set_page_config(
    page_title="러닝 크루 대시보드",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================
# 스타일
# =========================
st.markdown("""
<style>
.main {background-color:#f9fafb;padding:10px;}
.section-card {background:white;border-radius:12px;padding:20px;box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-bottom:20px;}
.weather-card {background:linear-gradient(135deg,#e0f7fa,#b2ebf2);border:2px solid #4dd0e1;border-radius:16px;padding:24px;}
.section-title {font-size:20px;font-weight:700;color:#1f2937;margin-bottom:12px;}
.subsection-title {font-size:15px;font-weight:600;color:#374151;margin-bottom:8px;}
</style>
""", unsafe_allow_html=True)

# =========================
# 날씨 데이터 (OpenWeatherMap)
# =========================
@st.cache_data(ttl=1800)
def fetch_weather_data():
    if not OPENWEATHER_API_KEY:
        return None, "OPENWEATHER_API_KEY 없음"

    try:
        url = (
            "https://api.openweathermap.org/data/2.5/forecast"
            "?q=Busan,KR"
            f"&appid={OPENWEATHER_API_KEY}"
            "&units=metric"
            "&lang=kr"
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        weather_list = []
        icon_map = {
            "01d": "☀️", "01n": "🌙",
            "02d": "⛅", "02n": "☁️",
            "03d": "☁️", "03n": "☁️",
            "04d": "☁️", "04n": "☁️",
            "09d": "🌧️", "09n": "🌧️",
            "10d": "🌦️", "10n": "🌧️",
            "11d": "⛈️", "11n": "⛈️",
            "13d": "❄️", "13n": "❄️",
            "50d": "🌫️", "50n": "🌫️"
        }

        # 하루 1개씩 (정오 기준 근접값)
        for item in data["list"][4::8][:7]:
            dt = datetime.fromtimestamp(item["dt"])
            day_kor = ["월", "화", "수", "목", "금", "토", "일"][dt.weekday()]
            temp = f"{round(item['main']['temp'])}°"
            icon_code = item["weather"][0]["icon"]
            icon = icon_map.get(icon_code, "🌤️")

            weather_list.append((day_kor, icon, temp))

        return weather_list, None

    except Exception as e:
        return None, str(e)

# =========================
# Notion 데이터
# =========================
@st.cache_data(ttl=300)
def fetch_notion_data():
    if not NOTION_TOKEN or not DATABASE_ID:
        return pd.DataFrame()

    try:
        notion = Client(auth=NOTION_TOKEN)
        response = notion.databases.query(database_id=DATABASE_ID)
        results = response.get("results", [])

        rows = []
        for r in results:
            p = r["properties"]

            date = (
                p.get("날짜", {})
                .get("date", {})
                .get("start", "")
            )

            runner = (
                p.get("러너", {})
                .get("select", {})
                .get("name", "Unknown")
            )

            distance = 0
            pace = None

            for k, v in p.items():
                if "거리" in k and v.get("number"):
                    distance = v["number"]
                if "페이스" in k and v.get("rich_text"):
                    if v["rich_text"]:
                        pace = v["rich_text"][0]["plain_text"]

            rows.append({
                "날짜": date,
                "러너": runner,
                "거리": distance,
                "페이스": pace
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df["날짜"] = pd.to_datetime(df["날짜"])
        return df

    except Exception as e:
        st.error(f"Notion 로드 실패: {e}")
        return pd.DataFrame()

# =========================
# 데이터 로드
# =========================
df = fetch_notion_data()

# =========================
# 🌤️ 날씨 섹션 (최상단)
# =========================
st.markdown('<div class="section-card weather-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🌤️ 부산 주간 날씨</div>', unsafe_allow_html=True)

weather_data, weather_error = fetch_weather_data()

if weather_data:
    cols = st.columns(len(weather_data))
    for i, (day, icon, temp) in enumerate(weather_data):
        with cols[i]:
            st.markdown(
                f"""
                <div style="background:white;border-radius:10px;padding:10px;text-align:center;">
                    <div style="font-size:14px;font-weight:600;">{day}</div>
                    <div style="font-size:26px;margin:6px 0;">{icon}</div>
                    <div style="font-size:14px;font-weight:700;">{temp}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
else:
    st.markdown(
        f"""
        <div style="text-align:center;color:#475569;padding:16px;">
            ❌ 날씨 정보를 불러오지 못했습니다<br>
            <small>{weather_error}</small>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown('</div>', unsafe_allow_html=True)

# =========================
# 📊 크루 현황 (기본)
# =========================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)

if df.empty:
    st.info("Notion 러닝 데이터가 없습니다.")
else:
    members = df["러너"].unique()[:4]
    crew_cols = st.columns(len(members))

    for idx, m in enumerate(members):
        md = df[df["러너"] == m]
        dist = md["거리"].sum()

        with crew_cols[idx]:
            st.markdown(f"### 🏃 {m}")
            st.metric("총 거리", f"{dist:.1f} km")

st.markdown('</div>', unsafe_allow_html=True)
