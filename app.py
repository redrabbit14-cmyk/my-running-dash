import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime
import requests

# 1. 설정 로드
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide")

# 2. 날씨 데이터 페칭 (오류 방지 강화)
@st.cache_data(ttl=1800)
def fetch_weather_data():
    if not OPENWEATHER_API_KEY:
        return "API 키 미설정"
    try:
        # 부산 좌표 (해운대/영도 인근)
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat=35.1796&lon=129.0756&appid={OPENWEATHER_API_KEY}&units=metric&lang=ko"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            weather_list = []
            for item in data['list'][::8][:5]: # 5일치 데이터
                dt = datetime.fromtimestamp(item['dt'])
                weather_list.append({
                    "day": dt.strftime("%m/%d") + f"({['월','화','수','목','금','토','일'][dt.weekday()]})",
                    "temp": f"{round(item['main']['temp'])}°",
                    "icon": f"http://openweathermap.org/img/wn/{item['weather'][0]['icon']}@2x.png",
                    "desc": item['weather'][0]['description']
                })
            return weather_list
        elif response.status_code == 401:
            return "API 키가 아직 활성화되지 않았습니다 (최대 2시간 소요)"
        else:
            return f"에러 코드: {response.status_code}"
    except Exception as e:
        return f"연결 실패: {str(e)}"

# 3. 노션 데이터 페칭
@st.cache_data(ttl=300)
def fetch_notion_data():
    if not NOTION_TOKEN or not DATABASE_ID: return pd.DataFrame()
    try:
        notion = Client(auth=NOTION_TOKEN)
        res = notion.databases.query(database_id=DATABASE_ID)
        rows = []
        for result in res.get("results", []):
            p = result.get("properties", {})
            date = p.get("날짜", {}).get("date", {}).get("start", "")[:10]
            runner = p.get("러너", {}).get("select", {}).get("name", "Unknown")
            dist = 0
            for k, v in p.items():
                if "거리" in k and v.get("number"):
                    dist = v["number"] / 1000 if v["number"] > 100 else v["number"]
            rows.append({"날짜": date, "러너": runner, "거리": dist})
        return pd.DataFrame(rows)
    except:
        return pd.DataFrame()

# --- 화면 레이아웃 ---
st.title("🏃‍♂️ 해운대-영도 러닝 크루 대시보드")

# 날씨 섹션 (가로 정렬)
st.subheader("🌦️ 부산 주간 날씨 예보")
weather_res = fetch_weather_data()

if isinstance(weather_res, list):
    cols = st.columns(len(weather_res))
    for i, w in enumerate(weather_res):
        with cols[i]:
            st.image(w['icon'], width=70)
            st.metric(w['day'], w['temp'])
            st.caption(w['desc'])
else:
    st.info(f"날씨 정보: {weather_res}")

st.divider()

# 데이터 섹션
df = fetch_notion_data()
if not df.empty:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("총 누적 거리", f"{df['거리'].sum():.2f} km")
        st.dataframe(df.sort_values("날짜", ascending=False), hide_index=True)
    with c2:
        st.bar_chart(df.groupby("러너")["거리"].sum())
else:
    st.warning("노션 데이터를 불러올 수 없습니다.")
