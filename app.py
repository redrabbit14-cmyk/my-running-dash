import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# Streamlit Secrets + 환경변수 모두 지원
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.environ.get("OPENWEATHER_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 간단한 CSS (에러 방지)
st.markdown("""
<style>
.section-card {background:white;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 4px 12px rgba(0,0,0,0.1);}
.weather-card {background:linear-gradient(135deg,#e0f7fa,#b2ebf2);border:2px solid #4dd0e1;border-radius:16px;padding:24px;text-align:center;}
.total-distance-card {background:linear-gradient(135deg,#ecfdf5,#d1fae5);border:2px solid #86efac;border-radius:16px;padding:24px;text-align:center;}
.notice-box {background:#eff6ff;border:2px solid #bfdbfe;border-radius:8px;padding:12px;margin-bottom:8px;}
.ai-box {background:linear-gradient(135deg,#faf5ff,#ede9fe);border:2px solid #c4b5fd;border-radius:16px;padding:24px;}
.section-title {font-size:24px;font-weight:800;color:#1f2937;margin-bottom:16px;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=1800)
def fetch_weather_data():
    if not OPENWEATHER_API_KEY:
        return None
    try:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q=Busan,KR&appid={OPENWEATHER_API_KEY}&units=metric&lang=ko"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            weather_list = []
            for item in data['list'][:8*7:8]:
                dt = datetime.fromtimestamp(item['dt'])
                day_kor = ['일','월','화','수','목','금','토'][dt.weekday()]
                temp = f"{item['main']['temp']:.0f}°"
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
            date_val = props.get("날짜", {}).get("date", {}).get("start", "")[:10] if props.get("날짜", {}).get("date") else ""
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            dist, elev, pace, photo_url = 0, 0, None, None
            for k, v in props.items():
                if "거리" in k and v.get("number"):
                    dist = v["number"] / 1000 if v["number"] > 100 else v["number"]
                if "고도" in k and v.get("number"):
                    elev = v["number"]
                if ("페이스" in k or "pace" in k.lower()) and v.get("rich_text"):
                    pace = v["rich_text"][0].get("plain_text", "")
                if ("사진" in k or "photo" in k.lower()):
                    if v.get("files"):
                        photo_url = v["files"][0].get("file", {}).get("url") or v["files"][0].get("external", {}).get("url")
                    elif v.get("url"):
                        photo_url = v["url"]
            data.append({"날짜": date_val, "러너": runner, "거리": dist, "고도": elev, "페이스": pace, "사진": photo_url})
        df = pd.DataFrame(data)
        if not df.empty and '날짜' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
        return df
    except:
        return pd.DataFrame()

def calculate_week_data(df, weeks_ago=0):
    if df.empty: return pd.DataFrame()
    end_date = datetime.now() - timedelta(days=weeks_ago * 7)
    start_date = end_date - timedelta(days=7)
    return df[(df['날짜'] >= start_date) & (df['날짜'] < end_date)]

# 데이터 로드
weather_data = fetch_weather_data()
df = fetch_notion_data()

# 1. 날씨 (맨 위!)
st.markdown('<div class="section-card weather-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🌤️ 부산 주간 날씨</div>', unsafe_allow_html=True)

if weather_data:
    cols = st.columns(7)
    for i, (day, icon, temp) in enumerate(weather_data):
        with cols[i]:
            st.markdown(f'''
            <div style="background:white;border-radius:12px;padding:16px;text-align:center;box-shadow:0 4px 12px rgba(0,0,0,0.1);">
                <div style="font-weight:800;font-size:14px;color:#1e293b;">{day}</div>
                <div style="font-size:32px;margin:8px 0;">{icon}</div>
                <div style="font-weight:900;font-size:20px;color:#047857;">{temp}</div>
            </div>
            ''', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;color:#6b7280;font-size:12px;margin-top:12px;">실시간 부산 날씨 | OpenWeatherMap</div>', unsafe_allow_html=True)
else:
    st.markdown('<div style="text-align:center;padding:32px;color:#6b7280;"><span style="font-size:48px;">🌤️</span><br>OPENWEATHER_API_KEY 설정 시 실제 날씨 표시</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# 2. 크루 현황
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)

st.markdown('<div style="font-size:18px;font-weight:700;color:#374151;margin-bottom:12px;">🏃 마라톤 대회</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">부산 벚꽃마라톤 - 1/10~2/15</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">경남 진해 군항제 - 2/1~3/10</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">부산 낙동강 - 1/20~2/28</div>', unsafe_allow_html=True)

if not df.empty:
    this_week = calculate_week_data(df, 0)
    last_week = calculate_week_data(df, 1)
    total_dist = this_week['거리'].sum()
    prev_dist = last_week['거리'].sum()
    percent_change = ((total_dist - prev_dist) / prev_dist * 100) if prev_dist > 0 else 0
    
    st.markdown('<div style="font-size:18px;font-weight:700;color:#374151;margin:20px 0 12px 0;">🎯 총 거리</div>', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="total-distance-card">
        <div style="font-size:48px;font-weight:900;color:#047857;margin-bottom:12px;">
            {total_dist:.1f}<span style="font-size:24px;color:#6b7280;"> km</span>
        </div>
        <div style="font-size:16px;color:#6b7280;">지난주: {prev_dist:.1f}km</div>
        <div style="font-size:18px;font-weight:800;color:{'#10b981' if percent_change >= 0 else '#ef4444'};">
            {"📈" if percent_change >= 0 else "📉"} {percent_change:+.0f}%
        </div>
    </div>
    ''', unsafe_allow_html=True)
else:
    st.markdown('<div class="total-distance-card"><div style="font-size:40px;color:#6b7280;">0.0 km</div></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# 3. 크루 컨디션
if not df.empty and len(df['러너'].unique()) > 0:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)
    
    crew_members = df['러너'].unique()[:4]
    col1, col2, col3, col4 = st.columns(4)
    
    for idx, member in enumerate(crew_members):
        member_data = df[df['러너'] == member]
        this_week_data = calculate_week_data(member_data, 0)
        week_dist = this_week_data['거리'].sum()
        
        with [col1, col2, col3, col4][idx]:
            st.markdown(f'''
            <div style="text-align:center;padding:16px;">
                <div style="width:60px;height:60px;border-radius:50%;background:#3b82f6;margin:0 auto 12px;display:flex;align-items:center;justify-content:center;font-size:24px;color:white;">👤</div>
                <div style="font-size:16px;font-weight:700;color:#1f2937;margin-bottom:16px;">{member}</div>
                <div style="background:#dbeafe;border-radius:8px;padding:8px;text-align:center;margin-bottom:8px;">
                    <div style="font-size:11px;color:#6b7280;">주간거리</div>
                    <div style="font-size:18px;font-weight:800;color:#1e40af;">{week_dist:.1f}km</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# 4. AI 코치
st.markdown('<div class="section-card ai-box">', unsafe_allow_html=True)
st.markdown('<div class="section-title">✨ AI 코치</div>', unsafe_allow_html=True)
st.markdown('<div style="background:white;border-radius:12px;padding:24px;text-align:center;color:#6b7280;">AI 코치 기능 준비 중입니다! 💪 모두 화이팅!</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# 푸터
st.markdown("---")
st.markdown('<div style="text-align:center;padding:24px;color:#6b7280;">🏃‍♂️ 러닝 크루 대시보드 | 날씨 + Notion 실시간 연동</div>', unsafe_allow_html=True)
