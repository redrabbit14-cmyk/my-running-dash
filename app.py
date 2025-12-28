import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.environ.get("OPENWEATHER_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide")

@st.cache_data(ttl=1800)
def fetch_weather_data():
    if not OPENWEATHER_API_KEY:
        return None
    try:
        url = "http://api.openweathermap.org/data/2.5/forecast?q=Busan,KR&appid=" + OPENWEATHER_API_KEY + "&units=metric&lang=ko"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            weather_list = []
            for item in data['list'][:8*7:8]:
                dt = datetime.fromtimestamp(item['dt'])
                day_kor = ['일','월','화','수','목','금','토'][dt.weekday()]
                temp = str(round(item['main']['temp'])) + "°"
                icon_code = item['weather'][0]['icon']
                icon_map = {
                    '01d': '☀️', '01n': '🌙', '02d': '⛅', '02n': '☁️',
                    '03d': '☁️', '03n': '☁️', '04d': '☁️', '04n': '☁️',
                    '09d': '🌧️', '09n': '🌧️', '10d': '🌦️', '10n': '🌧️',
                    '11d': '⛈️', '11n': '⛈️', '13d': '❄️', '13n': '❄️',
                    '50d': '🌫️', '50n': '🌫️'
                }
                icon = icon_map.get(icon_code, '🌤️')
                weather_list.append((day_kor, icon, temp))
            return weather_list
    except:
        pass
    return None

@st.cache_data(ttl=300)
def fetch_notion_data():
    if not NOTION_TOKEN or not DATABASE_ID:
        return pd.DataFrame()
    try:
        notion = Client(auth=NOTION_TOKEN)
        response = notion.databases.query(database_id=DATABASE_ID)
        data = []
        for row in response.get("results", []):
            props = row.get("properties", {})
            date_val = ""
            if "날짜" in props and props["날짜"].get("date"):
                date_val = props["날짜"]["date"].get("start", "")[:10]
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            dist = 0
            for k, v in props.items():
                if "거리" in k and v.get("number"):
                    dist = v["number"] / 1000 if v["number"] > 100 else v["number"]
            data.append({"날짜": date_val, "러너": runner, "거리": dist})
        df = pd.DataFrame(data)
        if not df.empty and '날짜' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
        return df
    except:
        return pd.DataFrame()

def calculate_week_data(df, weeks_ago=0):
    if df.empty:
        return pd.DataFrame()
    end_date = datetime.now() - timedelta(days=weeks_ago * 7)
    start_date = end_date - timedelta(days=7)
    return df[(df['날짜'] >= start_date) & (df['날짜'] < end_date)]

# 데이터 로드
weather_data = fetch_weather_data()
df = fetch_notion_data()

# 1. 날씨 - 가장 안전한 방법
st.markdown("""
<div style='background: linear-gradient(135deg, #e0f7fa, #b2ebf2); border-radius: 16px; padding: 24px; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(77,208,225,0.3); text-align: center;'>
    <h2 style='color: #1e2937; margin-bottom: 20px;'>🌤️ 부산 주간 날씨</h2>
""", unsafe_allow_html=True)

if weather_data:
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    cols = [col1, col2, col3, col4, col5, col6, col7]
    for i, (day, icon, temp) in enumerate(weather_data):
        with cols[i]:
            st.markdown(f"""
            <div style='background: white; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'>
                <div style='font-weight: bold; font-size: 16px; color: #1e2937;'>{day}</div>
                <div style='font-size: 36px; margin: 12px 0;'>{icon}</div>
                <div style='font-weight: bold; font-size: 22px; color: #047857;'>{temp}</div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown('<div style="color: #6b7280; font-size: 14px; margin-top: 16px;">실시간 부산 날씨 | OpenWeatherMap</div>', unsafe_allow_html=True)
else:
    st.markdown("""
        <div style='padding: 32px; color: #6b7280;'>
            <span style='font-size: 64px; display: block;'>🌤️</span>
            <div style='font-size: 20px; margin-top: 12px;'>OPENWEATHER_API_KEY 설정 시 실제 부산 날씨 표시</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# 2. 크루 현황 - 간단하게
st.markdown("""
<div style='background: white; border-radius: 16px; padding: 24px; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.12);'>
    <h2 style='color: #1f2937; margin-bottom: 20px;'>📊 크루 현황</h2>
""", unsafe_allow_html=True)

st.markdown("""
    <div style='background: #eff6ff; border: 2px solid #bfdbfe; border-radius: 12px; padding: 16px; margin-bottom: 16px;'>
        <strong>🏃 마라톤 대회</strong><br>
        부산 벚꽃마라톤 - 1/10~2/15<br>
        경남 진해 군항제 - 2/1~3/10<br>
        부산 낙동강 - 1/20~2/28
    </div>
""", unsafe_allow_html=True)

if not df.empty:
    this_week = calculate_week_data(df, 0)
    total_dist = this_week['거리'].sum()
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #ecfdf5, #d1fae5); border: 2px solid #86efac; border-radius: 20px; padding: 32px; text-align: center; box-shadow: 0 12px 40px rgba(16,185,129,0.25);'>
        <div style='font-size: 56px; font-weight: bold; color: #047857; margin-bottom: 16px;'>
            {total_dist:.1f} <span style='font-size: 28px; color: #6b7280;'>km</span>
        </div>
        <div style='font-size: 18px; color: #6b7280;'>이번주 총 주행거리</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style='background: linear-gradient(135deg, #ecfdf5, #d1fae5); border: 2px solid #86efac; border-radius: 20px; padding: 32px; text-align: center;'>
        <div style='font-size: 48px; color: #6b7280;'>0.0 km</div>
        <div style='font-size: 18px; color: #6b7280;'>Notion 데이터 로드 중</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# 3. 크루원
if not df.empty:
    st.markdown("""
    <div style='background: white; border-radius: 16px; padding: 24px; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(0,0,0,0.12);'>
        <h2 style='color: #1f2937; margin-bottom: 20px;'>👥 크루 컨디션</h2>
    """, unsafe_allow_html=True)
    
    crew_members = df['러너'].unique()[:4]
    col1, col2, col3, col4 = st.columns(4)
    
    for i, member in enumerate(crew_members):
        member_data = df[df['러너'] == member]
        this_week_data = calculate_week_data(member_data, 0)
        week_dist = this_week_data['거리'].sum()
        
        if i == 0: col = col1
        elif i == 1: col = col2
        elif i == 2: col = col3
        else: col = col4
        
        with col:
            st.markdown(f"""
            <div style='text-align: center; padding: 20px;'>
                <div style='width: 72px; height: 72px; border-radius: 50%; background: linear-gradient(135deg, #3b82f6, #60a5fa); margin: 0 auto 16px; display: flex; align-items: center; justify-content: center; font-size: 28px; color: white; box-shadow: 0 8px 24px rgba(59,130,246,0.3);'>👤</div>
                <div style='font-size: 16px; font-weight: bold; color: #1f2937; margin-bottom: 16px;'>{member}</div>
                <div style='background: #dbeafe; border-radius: 12px; padding: 12px;'>
                    <div style='font-size: 12px; color: #6b7280;'>주간거리</div>
                    <div style='font-size: 20px; font-weight: bold; color: #1e40af;'>{week_dist:.1f}km</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

# 4. AI 코치
st.markdown("""
<div style='background: linear-gradient(135deg, #faf5ff, #ede9fe); border: 2px solid #c4b5fd; border-radius: 20px; padding: 32px; text-align: center; margin-bottom: 24px; box-shadow: 0 12px 40px rgba(196,181,253,0.3);'>
    <h2 style='color: #1f2937; margin-bottom: 20px;'>✨ AI 코치</h2>
    <div style='background: white; border-radius: 16px; padding: 24px; color: #374151; font-size: 16px;'>
        💪 모두 화이팅! 꾸준히 달리면 목표 꼭 달성할 수 있어요! 🏃‍♂️
    </div>
</div>
""", unsafe_allow_html=True)

# 푸터
st.markdown("""
<div style='text-align: center; padding: 32px; color: #6b7280; background: #f8fafc; border-radius: 16px; margin-top: 24px;'>
    <div style='font-size: 18px; font-weight: 600; margin-bottom: 8px;'>🏃‍♂️ 러닝 크루 대시보드</div>
    <div style='font-size: 14px;'>날씨 + Notion 실시간 연동 | 부산 러닝 크루 화이팅!</div>
</div>
""", unsafe_allow_html=True)
