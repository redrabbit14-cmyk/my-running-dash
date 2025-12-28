import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 환경변수
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# CSS 스타일링
st.markdown("""
<style>
    .main { background-color: #f9fafb; padding: 10px; }
    .section-card { 
        background: white; border-radius: 12px; padding: 20px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 20px; 
    }
    .notice-box { 
        background: #eff6ff; border: 2px solid #bfdbfe; border-radius: 8px; 
        padding: 12px; margin-bottom: 8px; font-size: 14px; color: #1e40af; 
    }
    .weather-card {
        background: linear-gradient(135deg, #e0f7fa 0%, #b2ebf2 100%);
        border: 2px solid #4dd0e1; border-radius: 16px; padding: 24px; 
        text-align: center; box-shadow: 0 8px 25px rgba(77,208,225,0.2);
    }
    .total-distance-card {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border: 2px solid #86efac; border-radius: 16px; padding: 24px; 
        text-align: center; box-shadow: 0 8px 25px rgba(16,185,129,0.15);
    }
    .insight-box { 
        background: white; border-left: 5px solid; border-radius: 12px; 
        padding: 16px; margin: 12px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .insight-full { border-color: #10b981; background: #f0fdf4; }
    .insight-climb { border-color: #3b82f6; background: #eff6ff; }
    .insight-speed { border-color: #a855f7; background: #faf5ff; }
    .ai-box { 
        background: linear-gradient(135deg, #faf5ff 0%, #ede9fe 100%);
        border: 2px solid #c4b5fd; border-radius: 16px; padding: 24px;
    }
    .section-title { font-size: 24px; font-weight: 800; color: #1f2937; margin-bottom: 16px; }
    .subsection-title { font-size: 16px; font-weight: 700; color: #374151; margin-bottom: 12px; }
    .metric-card { 
        background: linear-gradient(135deg, #f8fafc, #f1f5f9); 
        border-radius: 12px; padding: 12px; text-align: center; 
        border: 1px solid #e2e8f0; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .stButton > button { 
        background: linear-gradient(135deg, #a855f7, #9333ea); 
        color: white; border: none; border-radius: 12px; padding: 12px 24px; 
        font-weight: 700; width: 100%; font-size: 16px; 
    }
    .stButton > button:hover { 
        transform: translateY(-2px); box-shadow: 0 8px 25px rgba(168,85,247,0.4); 
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=1800)
def fetch_weather_data():
    """부산 7일 날씨 데이터"""
    if not OPENWEATHER_API_KEY:
        return None
    try:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q=Busan,KR&appid={OPENWEATHER_API_KEY}&units=metric&lang=kr"
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
                weather_list.append((day_kor, icon, temp, item['weather'][0]['description']))
            return weather_list
    except:
        return None

@st.cache_data(ttl=300)
def fetch_notion_data():
    """Notion 데이터"""
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
    except Exception as e:
        st.error(f"Notion 오류: {e}")
        return pd.DataFrame()

def calculate_week_data(df, weeks_ago=0):
    if df.empty: return pd.DataFrame()
    end_date = datetime.now() - timedelta(days=weeks_ago * 7)
    start_date = end_date - timedelta(days=7)
    return df[(df['날짜'] >= start_date) & (df['날짜'] < end_date)]

def pace_to_seconds(pace_str):
    if not isinstance(pace_str, str) or ':' not in pace_str: return 999999
    try:
        parts = pace_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except: return 999999

def get_ai_recommendation(crew_data):
    return "AI 코치 기능은 Anthropic API 키 설정 후 사용 가능합니다!"

# 데이터 로드
weather_data = fetch_weather_data()
df = fetch_notion_data()

# 1. 날씨 (첫 번째!)
with st.container():
    st.markdown('<div class="section-card weather-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🌤️ 부산 주간 날씨</div>', unsafe_allow_html=True)
    if weather_data:
        cols = st.columns(7)
        for i, (day, icon, temp, desc) in enumerate(weather_data):
            with cols[i]:
                st.markdown(f"""
                <div style='border-radius:12px;padding:16px;background:white;box-shadow:0 4px 12px rgba(0,0,0,0.1);'>
                    <div style='font-weight:800;font-size:14px;color:#1e293b;'>{day}</div>
                    <div style='font-size:32px;margin:8px 0;'>{icon}</div>
                    <div style='font-weight:900;font-size:20px;color:#047857;'>{temp}</div>
                    <div style='font-size:12px;color:#6b7280;'>{desc}</div>
                </div>
                """, unsafe_allow_html=True)
        st.caption("📍 부산 | OpenWeatherMap 실시간 데이터")
    else:
        st.info("🌤️ OPENWEATHER_API_KEY 설정 시 실제 부산 날씨 표시")
    st.markdown('</div>', unsafe_allow_html=True)

# 2. 크루 현황
with st.container():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)
    
    # 마라톤 안내
    st.markdown('<div class="subsection-title">🏃 마라톤 대회</div>', unsafe_allow_html=True)
    for notice in ["부산 벚꽃마라톤 - 1/10~2/15", "경남 진해 군항제 - 2/1~3/10", "부산 낙동강 - 1/20~2/28"]:
        st.markdown(f'<div class="notice-box">{notice}</div>', unsafe_allow_html=True)
    
    # 총 거리
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown('<div class="subsection-title">🎯 총 거리</div>', unsafe_allow_html=True)
        if not df.empty:
            this_week = calculate_week_data(df, 0)
            last_week = calculate_week_data(df, 1)
            total_dist = this_week['거리'].sum()
            prev_dist = last_week['거리'].sum()
            percent_change = ((total_dist - prev_dist) / prev_dist * 100) if prev_dist > 0 else 0
            trend_icon = "📈" if percent_change >= 0 else "📉"
            trend_color = "#10b981" if percent_change >= 0 else "#ef4444"
            st.markdown(f'''
            <div class="total-distance-card">
                <div style="font-size:48px;font-weight:900;color:#047857;margin-bottom:12px;">
                    {total_dist:.1f}<span style="font-size:24px;color:#6b7280;"> km</span>
                </div>
                <div style="font-size:16px;color:#6b7280;">지난주: {prev_dist:.1f}km</div>
                <div style="font-size:18px;font-weight:800;color:{trend_color};">{trend_icon} {percent_change:+.0f}%</div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown('<div class="total-distance-card"><h1 style="color:#6b7280;">0.0 km</h1></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 3. 크루 컨디션
if not df.empty:
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)
        crew_members = df['러너'].unique()[:4]
        cols = st.columns(4)
        for idx, member in enumerate(crew_members):
            member_data = df[df['러너'] == member]
            this_week_data = calculate_week_data(member_data, 0)
            last_week_data = calculate_week_data(member_data, 1)
            week_dist = this_week_data['거리'].sum()
            prev_week_dist = last_week_data['거리'].sum()
            dist_change = ((week_dist - prev_week_dist) / prev_week_dist * 100) if prev_week_dist > 0 else 0
            avg_pace = "5:30" if this_week_data['페이스'].isna().all() else this_week_data['페이스'].dropna().iloc[0]
            last_run = this_week_data['날짜'].max()
            rest_days = (datetime.now() - last_run).days if pd.notna(last_run) else 7
            photo_url = member_data[member_data['사진'].notna()].sort_values('날짜', ascending=False).iloc[0]['사진'] if not member_data[member_data['사진'].notna()].empty else None
            
            with cols[idx]:
                if photo_url:
                    st.markdown(f'<img src="{photo_url}" style="width:60px;height:60px;border-radius:50%;object-fit:cover;border:3px solid white;box-shadow:0 4px 12px rgba(0,0,0,0.15);margin:0 auto 12px;display:block;">', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#3b82f6,#60a5fa);margin:0 auto 12px 0;display:flex;align-items:center;justify-content:center;font-size:24px;border:3px solid white;box-shadow:0 4px 12px rgba(0,0,0,0.15);">👤</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:14px;font-weight:700;color:#1f2937;text-align:center;margin-bottom:12px;">{member}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-card"><div style="font-size:11px;color:#6b7280;">주간거리</div><div style="font-size:16px;font-weight:800;color:#1e40af;">{week_dist:.1f}km</div></div>', unsafe_allow_html=True)
                trend_color = "#10b981" if dist_change >= 0 else "#ef4444"
                st.markdown(f'<div class="metric-card"><div style="font-size:11px;color:#6b7280;">전주대비</div><div style="font-size:16px;font-weight:800;color:{trend_color};">{dist_change:+.0f}%</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-card"><div style="font-size:11px;color:#6b7280;">평균페이스</div><div style="font-size:16px;font-weight:800;color:#7c3aed;">{avg_pace}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-card"><div style="font-size:11px;color:#6b7280;">휴식</div><div style="font-size:16px;font-weight:800;color:#ea580c;">{rest_days}일</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# 4. 인사이트
if not df.empty:
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🎉 크루 인사이트</div>', unsafe_allow_html=True)
        this_week = calculate_week_data(df, 0)
        col1, col2, col3 = st.columns(3)
        
        # 최장거리
        if not this_week.empty:
            longest = this_week.loc[this_week['거리'].idxmax()]
            with col1:
                st.markdown(f'''
                <div class="insight-box insight-full">
                    <span style="font-size:28px;">🏃‍♂️</span>
                    <div>{longest['러너']} {longest['거리']:.1f}km</div>
                </div>
                ''', unsafe_allow_html=True)
        
        # 최고고도
        if this_week['고도'].sum() > 0:
            top_climb = this_week.loc[this_week['고도'].idxmax()]
            with col2:
                st.markdown(f'''
                <div class="insight-box insight-climb">
                    <span style="font-size:28px;">⛰️</span>
                    <div>{top_climb['러너']} {top_climb['고도']:.0f}m</div>
                </div>
                ''', unsafe_allow_html=True)
        
        # 최고속도
        if '페이스' in this_week.columns and not this_week['페이스'].isna().all():
            paces_data = this_week[this_week['페이스'].notna()].copy()
            paces_data['페이스_초'] = paces_data['페이스'].apply(pace_to_seconds)
            fastest = paces_data.loc[paces_data['페이스_초'].idxmin()]
            with col3:
                st.markdown(f'''
                <div class="insight-box insight-speed">
                    <span style="font-size:28px;">⚡</span>
                    <div>{fastest['러너']} {fastest['페이스']}</div>
                </div>
                ''', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# 5. AI 코치
with st.container():
    st.markdown('<div class="section-card ai-box">', unsafe_allow_html=True)
    st.markdown('<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;"><span style="font-size:28px;">✨</span><span class="section-title" style="margin:0;">AI 코치</span></div>', unsafe_allow_html=True)
    if st.button("🚀 훈련 추천 받기", use_container_width=True):
        st.info("🤖 Anthropic API 키 설정 후 사용 가능!")
    st.markdown('</div>', unsafe_allow_html=True)

# 푸터
st.markdown("---")
st.markdown("""
<div style='text-align:center;padding:24px;color:#6b7280;background:#f8fafc;border-radius:12px;'>
    <div style='font-size:16px;font-weight:600;'>🏃‍♂️ 러닝 크루 대시보드 v2.0</div>
    <div style='font-size:13px;'>날씨 + Notion + AI | 실시간 연동</div>
</div>
""", unsafe_allow_html=True)
