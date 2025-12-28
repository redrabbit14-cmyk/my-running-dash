import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.environ.get("OPENWEATHER_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.main {background-color:#f9fafb;padding:10px;}
.section-card {background:white;border-radius:12px;padding:20px;box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-bottom:20px;}
.notice-box {background:#eff6ff;border:2px solid #bfdbfe;border-radius:8px;padding:12px;margin-bottom:8px;font-size:14px;color:#1e40af;}
.weather-card {background:linear-gradient(135deg,#e0f7fa,#b2ebf2);border:2px solid #4dd0e1;border-radius:16px;padding:24px;text-align:center;}
.total-distance-card {background:linear-gradient(135deg,#ecfdf5,#d1fae5);border:2px solid #86efac;border-radius:16px;padding:24px;text-align:center;}
.insight-box {background:white;border-left:4px solid;border-radius:8px;padding:12px;margin:6px 0;box-shadow:0 1px 3px rgba(0,0,0,0.08);}
.insight-full {border-color:#10b981;background:#f0fdf4;}
.insight-climb {border-color:#3b82f6;background:#eff6ff;}
.insight-speed {border-color:#a855f7;background:#faf5ff;}
.ai-box {background:linear-gradient(135deg,#faf5ff,#ede9fe);border:2px solid #c4b5fd;border-radius:12px;padding:16px;}
.section-title {font-size:20px;font-weight:700;color:#1f2937;margin-bottom:12px;}
.subsection-title {font-size:15px;font-weight:600;color:#374151;margin-bottom:8px;}
.stButton>button {background:linear-gradient(135deg,#a855f7,#9333ea);color:white;border:none;border-radius:8px;padding:10px 20px;font-weight:600;width:100%;}
.metric-card {background:#dbeafe;border-radius:4px;padding:4px;margin:2px 0;text-align:center;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=1800)
def fetch_weather_data():
    if not OPENWEATHER_API_KEY: return None
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
                icon_map = {'01d':'☀️','01n':'🌙','02d':'⛅','02n':'☁️','03d':'☁️','03n':'☁️','04d':'☁️','04n':'☁️','09d':'🌧️','09n':'🌧️','10d':'🌦️','10n':'🌧️','11d':'⛈️','11n':'⛈️','13d':'❄️','13n':'❄️','50d':'🌫️','50n':'🌫️'}
                icon = icon_map.get(icon_code, '🌤️')
                weather_list.append((day_kor, icon, temp))
            return weather_list
    except: pass
    return None

@st.cache_data(ttl=300)
def fetch_notion_data():
    try:
        if not NOTION_TOKEN or not DATABASE_ID: return pd.DataFrame()
        notion = Client(auth=NOTION_TOKEN)
        response = notion.databases.query(database_id=DATABASE_ID)
        results = response.get("results", [])
        data = []
        for row in results:
            props = row.get("properties", {})
            date_val = ""
            if props.get("날짜", {}).get("date"):
                date_val = props["날짜"]["date"].get("start", "")[:10]
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            dist = 0
            elev = 0
            pace = None
            photo_url = None
            for k, v in props.items():
                if "거리" in k and v.get("number") is not None:
                    dist = v["number"] / 1000 if v["number"] > 100 else v["number"]
                if "고도" in k and v.get("number") is not None:
                    elev = v["number"]
                if "페이스" in k or "pace" in k.lower():
                    if v.get("rich_text") and len(v["rich_text"]) > 0:
                        pace = v["rich_text"][0].get("plain_text", "")
                if ("사진" in k or "photo" in k.lower() or "이미지" in k or "image" in k.lower()):
                    if v.get("files") and len(v["files"]) > 0:
                        photo_url = v["files"][0].get("file", {}).get("url") or v["files"][0].get("external", {}).get("url")
                    elif v.get("url"):
                        photo_url = v["url"]
            data.append({"날짜": date_val, "러너": runner, "거리": dist, "고도": elev, "페이스": pace, "사진": photo_url})
        df = pd.DataFrame(data)
        if not df.empty and '날짜' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'])
        return df
    except Exception as e:
        st.error("데이터 로드 실패: " + str(e))
        return pd.DataFrame()

def calculate_week_data(df, weeks_ago=0):
    if df.empty: return pd.DataFrame()
    end_date = datetime.now() - timedelta(days=weeks_ago * 7)
    start_date = end_date - timedelta(days=7)
    return df[(df['날짜'] >= start_date) & (df['날짜'] < end_date)]

def pace_to_seconds(pace_str):
    try:
        if isinstance(pace_str, str) and ':' in pace_str:
            parts = pace_str.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        return 999999
    except: return 999999

df = fetch_notion_data()

# 1. 날씨 (맨 위!)
st.markdown('<div class="section-card weather-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🌤️ 부산 주간 날씨</div>', unsafe_allow_html=True)

weather_data = fetch_weather_data()
if weather_data:
    weather_html = '<div style="display:flex;gap:4px;justify-content:space-between;">'
    for day, icon, temp in weather_data:
        weather_html += f'<div style="background:white;border-radius:6px;padding:6px 2px;text-align:center;flex:1;min-width:0;"><div style="font-weight:600;color:#475569;font-size:10px;">{day}</div><div style="font-size:20px;margin:2px 0;">{icon}</div><div style="font-weight:700;color:#1e293b;font-size:11px;">{temp}</div></div>'
    weather_html += '</div>'
    st.markdown(weather_html, unsafe_allow_html=True)
else:
    st.markdown('<div style="text-align:center;padding:20px;color:#6b7280;">🌤️ OPENWEATHER_API_KEY 설정 시 실제 부산 날씨 표시</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# 2. 원래 크루 현황 (완전 복원)
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)

st.markdown('<div class="subsection-title">🏃 마라톤 대회 신청 안내</div>',
