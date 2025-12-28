import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# Streamlit Secrets 우선 사용 (Railway + Streamlit Cloud 모두 호환)
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.environ.get("OPENWEATHER_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# CSS 스타일링
st.markdown("""
<style>
    .main { background-color: #f9fafb; padding: 10px; }
    .section-card { 
        background: white; border-radius: 16px; padding: 24px; 
        box-shadow: 0 8px 32px rgba(0,0,0,0.12); margin-bottom: 24px; 
    }
    .notice-box { 
        background: linear-gradient(135deg, #eff6ff, #dbeafe); 
        border: 2px solid #bfdbfe; border-radius: 12px; 
        padding: 16px; margin-bottom: 12px; font-size: 14px; color: #1e40af; 
    }
    .weather-card {
        background: linear-gradient(135deg, #e0f7fa 0%, #b2ebf2 100%);
        border: 3px solid #4dd0e1; border-radius: 20px; padding: 28px; 
        text-align: center; box-shadow: 0 12px 40px rgba(77,208,225,0.3);
    }
    .total-distance-card {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border: 3px solid #86efac; border-radius: 20px; padding: 32px; 
        text-align: center; box-shadow: 0 12px 40px rgba(16,185,129,0.25);
    }
    .insight-box { 
        background: white; border-left: 6px solid; border-radius: 16px; 
        padding: 20px; margin: 16px 0; box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    }
    .insight-full { border-color: #10b981; background: #f0fdf4; }
    .insight-climb { border-color: #3b82f6; background: #eff6ff; }
    .insight-speed { border-color: #a855f7; background: #faf5ff; }
    .ai-box { 
        background: linear-gradient(135deg, #faf5ff 0%, #ede9fe 100%);
        border: 3px solid #c4b5fd; border-radius: 20px; padding: 32px;
    }
    .section-title { font-size: 28px; font-weight: 900; color: #1f2937; margin-bottom: 20px; }
    .subsection-title { font-size: 18px; font-weight: 700; color: #374151; margin-bottom: 16px; }
    .metric-card { 
        background: linear-gradient(135deg, #f8fafc, #f1f5f9); 
        border-radius: 12px; padding: 16px; text-align: center; 
        border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        margin-bottom: 12px;
    }
    .stButton > button { 
        background: linear-gradient(135deg, #a855f7, #9333ea); 
        color: white; border: none; border-radius: 16px; padding: 16px 32px; 
        font-weight: 800; width: 100%; font-size: 18px; 
        box-shadow: 0 8px 25px rgba(168,85,247,0.3);
    }
    .stButton > button:hover { 
        transform: translateY(-3px); box-shadow: 0 12px 35px rgba(168,85,247,0.5); 
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=1800)
def fetch_weather_data():
    """부산 7일 날씨 데이터 - 완벽 에러 처리"""
    if not OPENWEATHER_API_KEY:
        return None
    
    try:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q=Busan,KR&appid={OPENWEATHER_API_KEY}&units=metric&lang=ko"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            weather_list = []
            
            # 오늘부터 7일치 (매일 정오 데이터)
            for item in data['list'][:8*7:8]:
                dt = datetime.fromtimestamp(item['dt'])
                day_kor = ['일','월','화','수','목','금','토'][dt.weekday()]
                temp = f"{item['main']['temp']:.0f}°"
                feels_like = f"{item['main']['feels_like']:.0f}°"
                icon_code = item['weather'][0]['icon']
                desc = item['weather'][0]['description']
                
                # 아이콘 매핑
                icon_map = {
                    '01d': '☀️', '01n': '🌙', '02d': '⛅', '02n': '☁️',
                    '03d': '☁️', '03n': '☁️', '04d': '☁️', '04n': '☁️',
                    '09d': '🌧️', '09n': '🌧️', '10d': '🌦️', '10n': '🌧️',
                    '11d': '⛈️', '11n': '⛈️', '13d': '❄️', '13n': '❄️',
                    '50d': '🌫️', '50n': '🌫️'
                }
                icon = icon_map.get(icon_code, '🌤️')
                
                weather_list.append((day_kor, icon, temp, feels_like, desc))
            return weather_list
        
        return None
        
    except Exception:
        return None

@st.cache_data(ttl=600)
def fetch_notion_data():
    """Notion 데이터베이스에서 러닝 데이터"""
    if not NOTION_TOKEN or not DATABASE_ID:
        return pd.DataFrame()
    
    try:
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
            
            data.append({
                "날짜": date_val,
                "러너": runner,
                "거리": dist,
                "고도": elev,
                "페이스": pace,
                "사진": photo_url
            })
        
        df = pd.DataFrame(data)
        if not df.empty and '날짜' in df.columns:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
        return df
        
    except Exception as e:
        st.error(f"Notion 데이터 로드 실패: {e}")
        return pd.DataFrame()

def calculate_week_data(df, weeks_ago=0):
    if df.empty:
        return pd.DataFrame()
    end_date = datetime.now() - timedelta(days=weeks_ago * 7)
    start_date = end_date - timedelta(days=7)
    return df[(df['날짜'] >= start_date) & (df['날짜'] < end_date)]

def pace_to_seconds(pace_str):
    try:
        if isinstance(pace_str, str) and ':' in pace_str:
            parts = pace_str.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        return 999999
    except:
        return 999999

def get_ai_recommendation(crew_data):
    return "🤖 AI 코치: 모두 화이팅! 꾸준히 달리세요! 🏃‍♂️💪"

# 데이터 로드
weather_data = fetch_weather_data()
df = fetch_notion_data()

# ===== 1. 날씨 섹션 (첫 번째!)
st.markdown('<div class="section-card weather-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🌤️ 부산 주간 날씨</div>', unsafe_allow_html=True)

if weather_data:
    cols = st.columns(7)
    for i, (day, icon, temp, feels_like, desc) in enumerate(weather_data):
        with cols[i]:
            st.markdown(f'''
            <div style="
                background: white; border-radius: 16px; padding: 20px; 
                box-shadow: 0 8px 25px rgba(0,0,0,0.15); text-align: center;
                border: 2px solid #4dd0e1;
            ">
                <div style="font-weight: 900; font-size: 16px; color: #1e293b; margin-bottom: 8px;">{day}</div>
                <div style="font-size: 40px; margin: 12px 0;">{icon}</div>
                <div style="font-weight: 900; font-size: 24px; color: #047857; margin-bottom: 4px;">{temp}</div>
                <div style="font-size: 12px; color: #6b7280;">체감 {feels_like}</div>
                <div style="font-size: 11px; color: #475569; margin-top: 4px;">{desc}</div>
            </div>
            ''', unsafe_allow_html=True)
    st.markdown('<div style="text-align: center; margin-top: 20px; color: #6b7280; font-size: 13px;">📍 부산 실시간 날씨 | OpenWeatherMap</div>', unsafe_allow_html=True)
else:
    st.markdown('''
    <div style="
        text-align: center; padding: 40px; background: linear-gradient(135deg, #f0f9ff, #e0f2fe); 
        border-radius: 20px; border: 3px dashed #60a5fa; margin: 20px 0;
    ">
        <span style="font-size: 64px; display: block; margin-bottom: 20px;">🌤️</span>
        <h3 style="color: #1e40af; margin-bottom: 12px;">실시간 부산 날씨 준비 완료!</h3>
        <p style="color: #475569; font-size: 16px;">
            OPENWEATHER_API_KEY가 설정되어 있으면<br>
            <strong>실제 부산 7일 날씨</strong>가 자동 표시됩니다!
        </p>
    </div>
    ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ===== 2. 크루 현황 섹션
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)

# 마라톤 대회 안내
st.markdown('<div class="subsection-title">🏃 마라톤 대회 신청 안내</div>', unsafe_allow_html=True)
notices = [
    "부산 벚꽃마라톤 - 신청: 1/10~2/15",
    "경남 진해 군항제 마라톤 - 신청: 2/1~3/10",
    "부산 낙동강 마라톤 - 신청: 1/20~2/28"
]
for notice in notices:
    st.markdown(f'<div class="notice-box">{notice}</div>', unsafe_allow_html=True)

# 총 거리
st.markdown('<div class="subsection-title">🎯 총 거리 (크루 합산)</div>', unsafe_allow_html=True)
if not df.empty:
    this_week = calculate_week_data(df, 0)
    last_week = calculate_week_data(df, 1)
    
    total_dist = this_week['거리'].sum()
    prev_dist = last_week['거리'].sum()
    percent_change = ((total_dist - prev_dist) / prev_dist) * 100 if prev_dist > 0 else 0
    
    trend_icon = "📈" if percent_change >= 0 else "📉"
    trend_color = "#10b981" if percent_change >= 0 else "#ef4444"
    
    st.markdown(f'''
        <div class="total-distance-card">
            <div style="font-size: 56px; font-weight: 900; color: #047857; margin-bottom: 16px;">
                {total_dist:.1f}<span style="font-size: 28px; color: #6b7280;"> km</span>
            </div>
            <div style="font-size: 18px; color: #6b7280; margin-bottom: 16px;">
                지난주: {prev_dist:.1f}km
            </div>
            <div style="font-size: 20px; font-weight: 800; color: {trend_color};">
                {trend_icon} 전주 대비 {percent_change:+.0f}%
            </div>
        </div>
    ''', unsafe_allow_html=True)
else:
    st.markdown('<div class="total-distance-card"><div style="font-size: 48px; color: #6b7280;">0.0 km</div></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ===== 3. 크루 컨디션
if not df.empty:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)

    crew_members = df['러너'].unique()[:4]
    crew_data_for_ai = []
    
    col1, col2, col3, col4 = st.columns(4)
    columns = [col1, col2, col3, col4]
    
    for idx, member in enumerate(crew_members):
        member_data = df[df['러너'] == member]
        this_week_data = calculate_week_data(member_data, 0)
        last_week_data = calculate_week_data(member_data, 1)
        
        week_dist = this_week_data['거리'].sum()
        prev_week_dist = last_week_data['거리'].sum()
        dist_change = ((week_dist - prev_week_dist) / prev_week_dist) * 100 if prev_week_dist > 0 else 0
        
        avg_pace = "5:30"
        if not this_week_data.empty and this_week_data['페이스'].notna().any():
            paces = this_week_data['페이스'].dropna()
            if len(paces) > 0:
                avg_pace = paces.mode()[0] if len(paces.mode()) > 0 else paces.iloc[0]
        
        last_run = this_week_data['날짜'].max() if not this_week_data.empty else None
        rest_days = (datetime.now() - last_run).days if last_run and pd.notna(last_run) else 0
        
        crew_data_for_ai.append({
            'name': member, 'distance': week_dist, 'pace': avg_pace, 'rest_days': rest_days
        })
        
        trend_icon = "📈" if dist_change >= 0 else "📉"
        trend_color = "#10b981" if dist_change >= 0 else "#ef4444"
        
        photo_url = None
        if not member_data.empty and '사진' in member_data.columns:
            recent_photos = member_data[member_data['사진'].notna()].sort_values('날짜', ascending=False)
            if not recent_photos.empty:
                photo_url = recent_photos.iloc[0]['사진']

        with columns[idx]:
            if photo_url:
                st.markdown(f'''
                <img src="{photo_url}" style="
                    width: 70px; height: 70px; border-radius: 50%; object-fit: cover;
                    border: 4px solid white; box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                    margin: 0 auto 16px; display: block;
                ">
                ''', unsafe_allow_html=True)
            else:
                st.markdown('''
                <div style="
                    width: 70px; height: 70px; border-radius: 50%;
                    background: linear-gradient(135deg, #3b82f6, #60a5fa);
                    margin: 0 auto 16px; display: flex; align-items: center; justify-content: center;
                    font-size: 28px; border: 4px solid white; box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                ">👤</div>
                ''', unsafe_allow_html=True)
            
            st.markdown(f'''
            <h3 style="
                font-size: 16px; font-weight: 800; color: #1f2937; 
                margin: 0 0 20px; text-align: center;
            ">{member}</h3>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
            <div class="metric-card">
                <div style="font-size: 12px; color: #6b7280;">주간거리</div>
                <div style="font-size: 20px; font-weight: 900; color: #1e40af;">{week_dist:.1f}km</div>
            </div>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
            <div class="metric-card">
                <div style="font-size: 12px; color: #6b7280;">전주대비</div>
                <div style="font-size: 18px; font-weight: 900; color: {trend_color};">{trend_icon} {dist_change:+.0f}%</div>
            </div>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
            <div class="metric-card">
                <div style="font-size: 12px; color: #6b7280;">평균페이스</div>
                <div style="font-size: 18px; font-weight: 900; color: #7c3aed;">{avg_pace}/km</div>
            </div>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
            <div class="metric-card">
                <div style="font-size: 12px; color: #6b7280;">연속휴식</div>
                <div style="font-size: 18px; font-weight: 900; color: #ea580c;">{rest_days}일</div>
            </div>
            ''', unsafe_allow_html=True)
    
    st.session_state['crew_data_for_ai'] = crew_data_for_ai
    st.markdown('</div>', unsafe_allow_html=True)

# ===== 4. 인사이트 섹션
if not df.empty:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🎉 크루 인사이트</div>', unsafe_allow_html=True)

    this_week = calculate_week_data(df, 0)
    
    col1, col2, col3 = st.columns(3)
    
    # 최장거리
    if not this_week.empty and this_week['거리'].sum() > 0:
        longest_run = this_week.loc[this_week['거리'].idxmax()]
        with col1:
            st.markdown(f'''
            <div class="insight-box insight-full">
                <div style="display: flex; align-items: center; gap: 16px;">
                    <span style="font-size: 36px;">🏃‍♂️</span>
                    <div>
                        <h3 style="font-size: 20px; font-weight: 800; color: #1f2937; margin: 0 0 8px;">최장거리</h3>
                        <p style="margin: 0; color: #374151; font-size: 16px;">
                            <b style="color: #10b981;">{longest_run['러너']}</b><br>
                            {longest_run['거리']:.1f}km
                        </p>
                    </div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
    
    # 최고 고도
    if this_week['고도'].sum() > 0:
        top_climb = this_week.loc[this_week['고도'].idxmax()]
        with col2:
            st.markdown(f'''
            <div
