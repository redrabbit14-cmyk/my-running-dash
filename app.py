import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. API 키 및 설정 로드
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.environ.get("OPENWEATHER_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# CSS 스타일 정의
st.markdown("""
<style>
.main {background-color:#f9fafb;padding:10px;}
.section-card {background:white;border-radius:12px;padding:20px;box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-bottom:20px;}
.weather-card {background:linear-gradient(135deg,#e0f7fa,#b2ebf2);border:2px solid #4dd0e1;border-radius:16px;padding:20px;text-align:center;}
.section-title {font-size:20px;font-weight:700;color:#1f2937;margin-bottom:12px;}
.weather-item {background:white;border-radius:8px;padding:10px 5px;text-align:center;flex:1;min-width:60px;box-shadow:0 2px 4px rgba(0,0,0,0.05);}
</style>
""", unsafe_allow_html=True)

# 2. 날씨 데이터 페칭 함수 (보완됨)
@st.cache_data(ttl=1800)
def fetch_weather_data():
    if not OPENWEATHER_API_KEY:
        return "API_KEY_MISSING"
    
    try:
        # 부산의 위도/경도 (해운대/영도 인근)
        lat, lon = 35.1796, 129.0756 
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ko"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 401:
            return "INVALID_API_KEY"
            
        if response.status_code == 200:
            data = response.json()
            weather_list = []
            # 3시간 간격 데이터 중 하루 단위로 추출 (8개씩 건너뜀)
            for item in data['list'][::8][:7]:
                dt = datetime.fromtimestamp(item['dt'])
                day_kor = ['일','월','화','수','목','금','토'][dt.weekday()]
                temp = f"{round(item['main']['temp'])}°"
                icon_code = item['weather'][0]['icon']
                
                icon_map = {
                    '01d':'☀️','01n':'🌙','02d':'⛅','02n':'☁️','03d':'☁️','03n':'☁️',
                    '04d':'☁️','04n':'☁️','09d':'🌧️','09n':'🌧️','10d':'🌦️','10n':'🌧️',
                    '11d':'⛈️','11n':'⛈️','13d':'❄️','13n':'❄️','50d':'🌫️','50n':'🌫️'
                }
                icon = icon_map.get(icon_code, '🌤️')
                weather_list.append((day_kor, icon, temp))
            return weather_list
        else:
            return f"ERROR_{response.status_code}"
    except Exception as e:
        return f"EXCEPTION_{str(e)}"

# 3. 노션 데이터 페칭 함수
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
            
            # 거리 계산 로직 보완
            dist = 0
            for k, v in props.items():
                if "거리" in k and v.get("number") is not None:
                    n = v["number"]
                    dist = n / 1000 if n > 100 else n # m단위면 km로 변환
            
            data.append({"날짜": date_val, "러너": runner, "거리": dist})
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'])
        return df
    except Exception as e:
        return pd.DataFrame()

# --- 화면 구성 ---

# 1. 날씨 섹션
st.markdown('<div class="section-card weather-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🌤️ 부산 주간 날씨 (러닝 예보)</div>', unsafe_allow_html=True)

weather_result = fetch_weather_data()

if isinstance(weather_result, list):
    weather_html = '<div style="display:flex; gap:10px; justify-content:center; flex-wrap:nowrap; overflow-x:auto;">'
    for day, icon, temp in weather_result:
        weather_html += f'''
        <div class="weather-item">
            <div style="font-weight:600; color:#475569; font-size:12px;">{day}</div>
            <div style="font-size:24px; margin:5px 0;">{icon}</div>
            <div style="font-weight:700; color:#1e293b; font-size:14px;">{temp}</div>
        </div>
        '''
    weather_html += '</div>'
    st.markdown(weather_html, unsafe_allow_html=True)
elif weather_result == "INVALID_API_KEY":
    st.error("OpenWeather API 키가 유효하지 않습니다. Secrets 설정을 확인해주세요.")
elif weather_result == "API_KEY_MISSING":
    st.warning("OPENWEATHER_API_KEY가 설정되지 않았습니다.")
else:
    st.info(f"날씨 정보를 불러오는 중입니다... ({weather_result})")

st.markdown('</div>', unsafe_allow_html=True)

# 2. 크루 현황 섹션
df = fetch_notion_data()
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)

if not df.empty:
    total_dist = df['거리'].sum()
    st.metric("크루 누적 거리", f"{total_dist:.2f} km")
    st.dataframe(df, use_container_width=True)
else:
    st.write("노션에서 데이터를 불러올 수 없습니다. 환경변수(TOKEN, ID)를 확인해주세요.")

st.markdown('</div>', unsafe_allow_html=True)
