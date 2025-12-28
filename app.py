import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 변수 설정
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일 (기존 디자인 스타일 강화)
st.markdown("""
<style>
.section-card {background:white; border-radius:12px; padding:20px; box-shadow:0 4px 12px rgba(0,0,0,0.08); margin-bottom:20px;}
.weather-card {background:linear-gradient(135deg,#e0f7fa,#b2ebf2); border:2px solid #4dd0e1; border-radius:16px; padding:20px; text-align:center;}
.insight-box {background:white; border-left:4px solid; border-radius:8px; padding:12px; margin:6px 0; box-shadow:0 1px 3px rgba(0,0,0,0.08);}
.insight-full {border-color:#10b981; background:#f0fdf4;}
.insight-climb {border-color:#3b82f6; background:#eff6ff;}
.insight-speed {border-color:#a855f7; background:#faf5ff;}
.section-title {font-size:20px; font-weight:700; color:#1f2937; margin-bottom:12px;}
</style>
""", unsafe_allow_html=True)

# 3. 날씨 데이터 (디버깅 강화형)
@st.cache_data(ttl=1800)
def fetch_weather_data():
    if not OPENWEATHER_API_KEY: return None
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat=35.1796&lon=129.0756&appid={OPENWEATHER_API_KEY}&units=metric&lang=ko"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return [(datetime.fromtimestamp(i['dt']).strftime('%m/%d'), 
                     f"http://openweathermap.org/img/wn/{i['weather'][0]['icon']}@2x.png", 
                     f"{round(i['main']['temp'])}°") for i in data['list'][::8][:6]]
    except: return None
    return None

# 4. 노션 데이터 (사진, 고도, 페이스 포함)
@st.cache_data(ttl=300)
def fetch_notion_data():
    if not NOTION_TOKEN or not DATABASE_ID: return pd.DataFrame()
    try:
        notion = Client(auth=NOTION_TOKEN)
        response = notion.databases.query(database_id=DATABASE_ID)
        data = []
        for row in response.get("results", []):
            props = row.get("properties", {})
            date = props.get("날짜", {}).get("date", {}).get("start", "")[:10]
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            # 거리/고도/페이스 추출
            dist = 0
            elev = 0
            pace = "00:00"
            photo = ""
            for k, v in props.items():
                if "거리" in k and v.get("number"): dist = v["number"] / 1000 if v["number"] > 100 else v["number"]
                if "고도" in k and v.get("number"): elev = v["number"]
                if ("페이스" in k or "pace" in k.lower()) and v.get("rich_text"): pace = v["rich_text"][0].get("plain_text", "00:00")
                if ("사진" in k or "이미지" in k) and v.get("files"): 
                    photo = v["files"][0].get("file", {}).get("url") or v["files"][0].get("external", {}).get("url")
            
            data.append({"날짜": date, "러너": runner, "거리": dist, "고도": elev, "페이스": pace, "사진": photo})
        
        df = pd.DataFrame(data)
        if not df.empty: df['날짜'] = pd.to_datetime(df['날짜'])
        return df
    except: return pd.DataFrame()

# 페이스 계산용 함수
def pace_to_seconds(p):
    try: return int(p.split(':')[0])*60 + int(p.split(':')[1])
    except: return 9999

# --- 메인 화면 시작 ---
df = fetch_notion_data()

# [1. 날씨]
st.markdown('<div class="section-card weather-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🌤️ 부산 주간 날씨 (영도/해운대)</div>', unsafe_allow_html=True)
weather = fetch_weather_data()
if weather:
    cols = st.columns(len(weather))
    for i, (day, icon, temp) in enumerate(weather):
        with cols[i]:
            st.write(f"**{day}**")
            st.image(icon, width=50)
            st.write(f"**{temp}**")
else:
    st.info("API 키 승인 대기 중이거나 설정 오류입니다.")
st.markdown('</div>', unsafe_allow_html=True)

# [2. 크루 현황 및 사진]
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 멤버별 주간 현황</div>', unsafe_allow_html=True)

if not df.empty:
    this_week = df[df['날짜'] >= (datetime.now() - timedelta(days=7))]
    last_week = df[(df['날짜'] < (datetime.now() - timedelta(days=7))) & (df['날짜'] >= (datetime.now() - timedelta(days=14)))]
    
    runners = df['러너'].unique()
    for r in runners:
        r_this = this_week[this_week['러너'] == r]['거리'].sum()
        r_last = last_week[last_week['러너'] == r]['거리'].sum()
        diff = r_this - r_last
        
        # 마지막 활동일로부터 휴식 기간 계산
        last_date = df[df['러너'] == r]['날짜'].max()
        rest_days = (datetime.now() - last_date).days
        
        col_img, col_txt = st.columns([1, 4])
        with col_img:
            r_photo = df[df['러너'] == r]['사진'].iloc[0]
            if r_photo: st.image(r_photo, width=80)
            else: st.write("👤")
        with col_txt:
            st.write(f"**{r} 러너** | 이번주: {r_this:.2f}km (전주대비 {'+' if diff>=0 else ''}{diff:.2f}km)")
            st.caption(f"현재 {rest_days}일째 휴식 중")
            st.progress(min(r_this / 20.0, 1.0)) # 주간 20km 목표 대비 게이지
st.markdown('</div>', unsafe_allow_html=True)

# [3. 명예의 전당 (인사이트)]
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🏆 이번 주 명예의 전당</div>', unsafe_allow_html=True)
if not this_week.empty:
    best_dist = this_week.loc[this_week['거리'].idxmax()]
    best_elev = this_week.loc[this_week['고도'].idxmax()]
    # 페이스는 초 단위로 변환 후 최소값(가장 빠른) 찾기
    this_week['pace_sec'] = this_week['페이스'].apply(pace_to_seconds)
    best_pace = this_week.loc[this_week['pace_sec'].idxmin()]
    
    st.markdown(f'<div class="insight-box insight-full">🏃 **최장 거리:** {best_dist["러너"]} ({best_dist["거리"]:.2f}km)</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="insight-box insight-climb">⛰️ **최고 고도:** {best_elev["러너"]} ({best_elev["고도"]}m)</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="insight-box insight-speed">⚡ **최고 페이스:** {best_pace["러너"]} ({best_pace["페이스"]}/km)</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
