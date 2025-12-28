import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests
import plotly.express as px
import plotly.graph_objects as go

# 페이지 설정 - 모바일 최적화
st.set_page_config(
    page_title="런닝 대시보드",
    page_icon="🏃‍♂️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 환경변수 또는 secrets에서 불러오기 (GitHub 안전)
NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
WEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY") or os.environ.get("OPENWEATHER_API_KEY")

@st.cache_data(ttl=300)  # 5분 캐시
def load_notion_data():
    if not NOTION_TOKEN or not DATABASE_ID:
        st.error("❌ Notion 토큰 또는 데이터베이스 ID가 없습니다. Streamlit secrets에 설정하세요.")
        st.stop()
    
    notion = Client(auth=NOTION_TOKEN)
    try:
        results = notion.databases.query(database_id=DATABASE_ID)
        data = []
        for page in results['results']:
            props = page['properties']
            row = {
                '날짜': props.get('날짜', {}).get('date', {}).get('start', '') or '',
                '거리(km)': float(props.get('거리', {}).get('number', 0) or 0),
                '시간': props.get('시간', {}).get('rich_text', [{}])[0].get('plain_text', '') or '0:00:00',
                '평균페이스': props.get('평균페이스', {}).get('rich_text', [{}])[0].get('plain_text', '') or '',
                '심박수': props.get('심박수', {}).get('number', 0) or 0,
                '상태': props.get('상태', {}).get('select', {}).get('name', '') or '',
                '날씨': props.get('날씨', {}).get('select', {}).get('name', '') or '',
                '코스': props.get('코스', {}).get('rich_text', [{}])[0].get('plain_text', '') or ''
            }
            data.append(row)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ Notion 데이터 로드 실패: {str(e)}")
        st.stop()

def get_weather(city="Seoul"):
    if not WEATHER_API_KEY:
        return None
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=kr"
        resp = requests.get(url).json()
        return {
            '온도': resp['main']['temp'],
            '습도': resp['main']['humidity'],
            '날씨': resp['weather'][0]['description'],
            '도시': city
        }
    except:
        return None

def parse_time_to_seconds(time_str):
    if not time_str or time_str == '0:00:00':
        return 0
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = map(int, parts)
        return h*3600 + m*60 + s
    return 0

# 메인 앱 시작
st.title("🏃‍♂️ 런닝 대시보드")
st.markdown("---")

# 현재 날씨 (오른쪽 상단)
weather = get_weather("Seoul")
if weather:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🌡️ 온도", f"{weather['온도']}°C")
    with col2:
        st.metric("💧 습도", f"{weather['습도']}%")
    with col3:
        st.metric("☁️", weather['날씨'])

# 데이터 로드
df = load_notion_data()

# 날짜 필터링 (최근 30일)
df['날짜'] = pd.to_datetime(df['날짜'])
recent_df = df[df['날짜'] >= (datetime.now() - timedelta(days=30))].copy()

if recent_df.empty:
    st.warning("최근 30일간 데이터가 없습니다.")
    st.stop()

# 시간 -> 초 변환
recent_df['시간_초'] = recent_df['시간'].apply(parse_time_to_seconds)
recent_df['페이스_분km'] = recent_df['시간_초'] / (recent_df['거리(km)'] * 60)

# 주요 통계 카드 (그림처럼 2x2 그리드)
col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

with col1:
    total_dist = recent_df['거리(km)'].sum()
    st.metric("📏 총거리", f"{total_dist:.1f}km", delta=None)

with col2:
    total_runs = len(recent_df)
    st.metric("🏃 런 횟수", f"{total_runs}회", delta=None)

with col3:
    avg_pace = recent_df['페이스_분km'].mean()
    st.metric("⏱️ 평균페이스", f"{avg_pace:.1f}'/km", delta=None)

with col4:
    avg_hr = recent_df['심박수'].mean()
    st.metric("❤️ 평균심박", f"{avg_hr:.0f}bpm", delta=None)

# 그래프 섹션
st.markdown("### 📊 런닝 추이")
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    # 거리 추이
    fig_dist = px.line(recent_df, x='날짜', y='거리(km)', 
                       title="거리 추이", markers=True)
    fig_dist.update_layout(height=300, showlegend=False)
    st.plotly_chart(fig_dist, use_container_width=True)

with col_chart2:
    # 페이스 추이
    fig_pace = px.line(recent_df, x='날짜', y='페이스_분km', 
                       title="페이스 추이", markers=True)
    fig_pace.update_layout(height=300, showlegend=False)
    st.plotly_chart(fig_pace, use_container_width=True)

# 최근 런 기록 테이블
st.markdown("### 📋 최근 기록")
st.dataframe(recent_df[['날짜', '거리(km)', '평균페이스', '심박수', '상태', '날씨']].tail(10),
             use_container_width=True, hide_index=True)

# 상태별 통계
st.markdown("### 🎯 상태별 분석")
status_counts = recent_df['상태'].value_counts()
fig_pie = px.pie(values=status_counts.values, names=status_counts.index, 
                 title="상태 분포")
fig_pie.update_layout(height=400)
st.plotly_chart(fig_pie, use_container_width=True)

# 모바일 최적화 CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none !important; }
    .main .block-container { padding-top: 1rem; padding-left: 1rem; padding-right: 1rem; }
    @media (max-width: 768px) {
        .main .block-container { padding: 0.5rem; }
    }
</style>
""", unsafe_allow_html=True)
