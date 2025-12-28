import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 변수 로드
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide")

# 2. 스타일 정의 (깨짐 방지를 위해 인라인 스타일 대신 클래스 활용)
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .runner-card { background: white; border-radius: 12px; padding: 15px; margin-bottom: 10px; border-left: 5px solid #3b82f6; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    .insight-card { padding: 12px; border-radius: 8px; margin-bottom: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# 3. 날씨 데이터 (안정성 최우선)
@st.cache_data(ttl=1800)
def fetch_weather_data():
    if not OPENWEATHER_API_KEY: return None
    try:
        # 부산(영도/해운대) 좌표 기준 5일 예보
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat=35.1796&lon=129.0756&appid={OPENWEATHER_API_KEY}&units=metric&lang=ko"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return [{"day": datetime.fromtimestamp(i['dt']).strftime('%m/%d(%a)'),
                     "icon": f"http://openweathermap.org/img/wn/{i['weather'][0]['icon']}@2x.png",
                     "temp": f"{round(i['main']['temp'])}°",
                     "desc": i['weather'][0]['description']} for i in data['list'][::8][:5]]
    except: return None
    return None

# 4. 노션 데이터 (모든 컬럼 복구)
@st.cache_data(ttl=300)
def fetch_notion_data():
    if not NOTION_TOKEN or not DATABASE_ID: return pd.DataFrame()
    try:
        notion = Client(auth=NOTION_TOKEN)
        res = notion.databases.query(database_id=DATABASE_ID)
        rows = []
        for row in res.get("results", []):
            p = row.get("properties", {})
            # 기본 정보 추출
            date_val = p.get("날짜", {}).get("date", {}).get("start", "2024-01-01")[:10]
            runner = p.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            # 거리, 고도, 페이스, 사진 정보
            dist = 0
            elev = 0
            pace = "00:00"
            photo = ""
            for k, v in p.items():
                if "거리" in k and v.get("number"): dist = v["number"] / 1000 if v["number"] > 100 else v["number"]
                if "고도" in k and v.get("number"): elev = v["number"]
                if ("페이스" in k or "pace" in k.lower()) and v.get("rich_text"): 
                    pace = v["rich_text"][0].get("plain_text", "00:00")
                if ("사진" in k or "이미지" in k) and v.get("files"):
                    files = v.get("files", [])
                    if files: photo = files[0].get("file", {}).get("url") or files[0].get("external", {}).get("url")

            rows.append({"날짜": date_val, "러너": runner, "거리": dist, "고도": elev, "페이스": pace, "사진": photo})
        
        df = pd.DataFrame(rows)
        if not df.empty: df['날짜'] = pd.to_datetime(df['날짜'])
        return df
    except: return pd.DataFrame()

def pace_to_seconds(p):
    try: return int(p.split(':')[0])*60 + int(p.split(':')[1])
    except: return 9999

# --- 화면 렌더링 ---
st.title("🏃‍♂️ 해운대-영도 러닝 크루 대시보드")

# [1. 날씨 섹션]
st.subheader("🌤️ 부산 주간 날씨 예보")
weather_data = fetch_weather_data()
if weather_data:
    cols = st.columns(len(weather_data))
    for i, w in enumerate(weather_data):
        with cols[i]:
            st.markdown(f"<div style='text-align:center;'><b>{w['day']}</b></div>", unsafe_allow_html=True)
            st.image(w['icon'], width=60)
            st.markdown(f"<div style='text-align:center; font-size:18px;'><b>{w['temp']}</b><br><small>{w['desc']}</small></div>", unsafe_allow_html=True)
else:
    st.warning("날씨 정보를 불러올 수 없습니다. API 키 활성화를 기다려주세요 (최대 2시간).")

st.divider()

# [2. 멤버별 현황 섹션 (사진/비교/휴식 포함)]
df = fetch_notion_data()
if not df.empty:
    st.subheader("📊 멤버별 주간 활동 (전주 대비)")
    
    # 시간 기준 설정
    today = datetime.now()
    this_week_start = today - timedelta(days=7)
    last_week_start = today - timedelta(days=14)
    
    runners = df['러너'].unique()
    for r in runners:
        rdf = df[df['러너'] == r]
        this_dist = rdf[rdf['날짜'] >= this_week_start]['거리'].sum()
        last_dist = rdf[(rdf['날짜'] >= last_week_start) & (rdf['날짜'] < this_week_start)]['거리'].sum()
        diff = this_dist - last_dist
        
        # 휴식 기간 계산
        last_run = rdf['날짜'].max()
        rest_days = (today - last_run).days
        
        # 레이아웃 구성
        with st.container():
            col_img, col_info, col_metric = st.columns([1, 3, 2])
            with col_img:
                photo_url = rdf['사진'].dropna().iloc[0] if not rdf['사진'].dropna().empty else None
                if photo_url: st.image(photo_url, width=80)
                else: st.markdown("### 👤")
            with col_info:
                st.markdown(f"### {r}")
                st.caption(f"마지막 활동: {last_run.strftime('%Y-%m-%d')} ({rest_days}일째 휴식 중)")
            with col_metric:
                st.metric("이번 주 거리", f"{this_dist:.2f} km", f"{diff:+.2f} km")
            st.markdown("---")

    # [3. 이번 주 명예의 전당]
    st.subheader("🏆 이번 주 부문별 TOP")
    tw_df = df[df['날짜'] >= this_week_start].copy()
    if not tw_df.empty:
        tw_df['pace_sec'] = tw_df['페이스'].apply(pace_to_seconds)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            top_d = tw_df.loc[tw_df['거리'].idxmax()]
            st.success(f"🥇 **최장 거리**\n\n{top_d['러너']} ({top_d['거리']:.2f}km)")
        with c2:
            top_e = tw_df.loc[tw_df['고도'].idxmax()]
            st.info(f"⛰️ **최고 고도**\n\n{top_e['러너']} ({top_e['고도']}m)")
        with c3:
            top_p = tw_df.loc[tw_df['pace_sec'].idxmin()]
            st.warning(f"⚡ **최고 페이스**\n\n{top_p['러너']} ({top_p['페이스']}/km)")
else:
    st.info("노션 데이터를 불러오는 중입니다...")
