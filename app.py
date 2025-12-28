import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.environ.get("OPENWEATHER_API_KEY")

def get_weather(city, api_key):
    """OpenWeatherMap API로 부산 날씨 정보 가져오기"""
    if not api_key:
        return None
    
    url = f"http://api.openweathermap.org/data/2.5/weather"
    params = {
        'q': city,
        'appid': api_key,
        'units': 'metric',  # 섭씨
        'lang': 'kr'  # 한국어
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"날씨 API 오류: {e}")
        return None

# Streamlit 앱 설정
st.set_page_config(page_title="부산 날씨 대시보드", layout="wide")

st.title("🌤️ 부산 날씨 대시보드")

# 사이드바 설정
with st.sidebar:
    st.header("📍 부산 날씨")
    city = st.text_input("도시", value="Busan", help="부산 기본 설정")
    if st.button("🔄 새로고침", use_container_width=True):
        st.rerun()

# 메인 날씨 표시
col1, col2 = st.columns([1, 1])

with col1:
    st.header("🌤️ 현재 날씨")
    weather_data = get_weather(city, OPENWEATHER_API_KEY)
    
    if weather_data:
        temp = weather_data['main']['temp']
        feels_like = weather_data['main']['feels_like']
        humidity = weather_data['main']['humidity']
        wind_speed = weather_data['wind']['speed']
        description = weather_data['weather'][0]['description']
        icon = weather_data['weather'][0]['icon']
        
        icon_url = f"http://openweathermap.org/img/wn/{icon}@2x.png"
        
        st.metric("🌡️ 기온", f"{temp:.1f}°C", f"{feels_like:.1f}°C")
        st.metric("💧 습도", f"{humidity}%")
        st.metric("🌪️ 바람", f"{wind_speed:.1f}m/s")
        st.image(icon_url, width=100)
        st.caption(description.title())
    else:
        st.warning("⚠️ OPENWEATHER_API_KEY를 secrets에 추가하세요")

with col2:
    st.header("📊 추가 정보")
    if weather_data:
        coord = weather_data['coord']
        st.metric("📍 위도/경도", f"{coord['lat']:.2f}/{coord['lon']:.2f}")
        st.metric("🌡️ 최저/최고", f"{weather_data['main']['temp_min']:.1f}°C / {weather_data['main']['temp_max']:.1f}°C")
        st.caption(f"기압: {weather_data['main']['pressure']}hPa")
        st.caption(f"구름: {weather_data['clouds']['all']}%")
    else:
        st.info("날씨 데이터를 불러오는 중...")

# Notion 부분 (원본 유지)
if NOTION_TOKEN and DATABASE_ID:
    st.header("📋 Notion 데이터베이스")
    try:
        notion = Client(auth=NOTION_TOKEN)
        results = notion.databases.query(database_id=DATABASE_ID)
        df = pd.DataFrame(results['results'])
        st.dataframe(df)
    except Exception as e:
        st.error(f"Notion 연결 오류: {e}")
else:
    st.info("Notion 설정 필요")

# 푸터
st.caption("부산 날씨 | OpenWeatherMap API [web:6]")
