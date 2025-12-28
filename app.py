import streamlit as st
from notion_client import Client
import pandas as pd
from datetime import datetime, timedelta
import requests
import plotly.express as px

# 페이지 설정
st.set_page_config(page_title="🏃‍♂️ 런닝 대시보드", layout="wide", initial_sidebar_state="collapsed")

# Secrets에서만 불러오기 (os.environ 제거)
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DATABASE_ID = st.secrets["DATABASE_ID"]
    WEATHER_API_KEY = st.secrets["OPENWEATHER_API_KEY"]
    st.success("✅ Secrets 정상 로드됨")
except:
    st.error("❌ Secrets 설정 확인 필요")
    st.stop()

@st.cache_data(ttl=600)
def load_notion_data():
    notion = Client(auth=NOTION_TOKEN)
    results = notion.databases.query(database_id=DATABASE_ID)
    
    data = []
    for page in results['results']:
        props = page['properties']
        row = {
            '날짜': props.get('날짜', {}).get('date', {}).get('start', ''),
            '거리(km)': float(props.get('거리', {}).get('number', 0)),
            '시간': props.get('시간', {}).get('rich_text', [{}])[0].get('plain_text', ''),
            '평균페이스': props.get('평균페이스', {}).get('rich_text', [{}])[0].get('plain_text', ''),
            '심박수': props.get('심박수', {}).get('number', 0),
            '상태': props.get('상태', {}).get('select', {}).get('name', ''),
            '날씨': props.get('날씨', {}).get('select', {}).get('name', '')
        }
        data.append(row)
    return pd.DataFrame(data)

def get_weather(city="Seoul"):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=kr"
        resp = requests.get(url, timeout=5).json()
        return resp['main']['temp'], resp['weather'][0]['description']
    except:
        return None, None

# 메인 앱
st.title("🏃‍♂️ 런닝 대시보드")

# 날씨
temp, desc = get_weather()
col1, col2 = st.columns(2)
col1.metric("🌡️ 서울", f"{temp}°C" if temp else "❓")
col2.metric("☁️", desc if desc else "로딩중")

# 데이터 로드
df = load_notion_data()
df['날짜'] = pd.to_datetime(df['날짜'])
recent_df = df.tail(30).copy()  # 최근 30건

if recent_df.empty:
    st.warning("⚠️ 노션 데이터베이스에 런닝 기록이 없습니다.")
    st.stop()

# 페이스 계산
def parse_time(time_str):
    if pd.isna(time_str) or not time_str: return 0
    parts = time_str.split(':')
    if len(parts) == 3: 
        return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
    return 0

recent_df['시간_초'] = recent_df['시간'].apply(parse_time)
recent_df['페이스'] = recent_df['시간_초'] / (recent_df['거리(km)'] * 60)

# 2x2 카드 (모바일 최적화)
col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

with col1: st.metric("📏 총거리", f"{recent_df['거리(km)'].sum():.1f}km")
with col2: st.metric("🏃 횟수", f"{len(recent_df)}회")
with col3: st.metric("⏱️ 평균페이스", f"{recent_df['페이스'].mean():.1f}'/km")
with col4: st.metric("❤️ 평균심박", f"{recent_df['심박수'].mean():.0f}bpm")

# 그래프
col1, col2 = st.columns(2)
with col1:
    fig1 = px.line(recent_df, x='날짜', y='거리(km)', markers=True, title="거리")
    st.plotly_chart(fig1, use_container_width=True)
with col2:
    fig2 = px.line(recent_df, x='날짜', y='페이스', markers=True, title="페이스")
    st.plotly_chart(fig2, use_container_width=True)

# 최근 기록
st.subheader("📋 최근 기록")
st.dataframe(recent_df[['날짜', '거리(km)', '평균페이스', '심박수', '상태']].tail(10), 
             use_container_width=True, hide_index=True)
