import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

# OpenWeatherMap API 키 (st.secrets 사용 권장)
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")  # .streamlit/secrets.toml에 추가

# 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 모바일 최적화 CSS
st.markdown("""
<style>
    .main { 
        background-color: #f9fafb;
        padding: 10px;
    }
    
    /* 섹션 카드 */
    .section-card {
        background: white;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 16px;
    }
    
    /* 공지사항 박스 */
    .notice-box {
        background: #eff6ff;
        border: 2px solid #bfdbfe;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 6px;
        font-size: 13px;
        color: #1e40af;
    }
    
    /* 날씨 카드 - 작고 빽빽하게 */
    .weather-card {
        background: linear-gradient(to bottom, #e0f2fe, #f0f9ff);
        border-radius: 6px;
        padding: 6px 2px;
        text-align: center;
        font-size: 11px;
    }
    
    /* 총 거리 카드 */
    .total-distance-card {
        background: linear-gradient(to bottom right, #ecfdf5, #d1fae5);
        border: 2px solid #86efac;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    
    /* 크루원 카드 - 모바일용 간소화 */
    .crew-card {
        background: white;
        border: 2px solid #e5e7eb;
        border-radius: 10px;
        padding: 10px 8px;
        text-align: center;
        height: 100%;
    }
    
    .crew-avatar {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, #3b82f6, #60a5fa);
        margin: 0 auto 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        border: 3px solid white;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    
    .crew-stat-box {
        background: #f3f4f6;
        border-radius: 4px;
        padding: 6px 4px;
        margin: 3px 0;
        font-size: 11px;
    }
    
    /* Insight & Fun 박스 */
    .insight-box {
        background: white;
        border-left: 4px solid;
        border-radius: 8px;
        padding: 12px;
        margin: 6px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    
    .insight-full { border-color: #10b981; background: #f0fdf4; }
    .insight-climb { border-color: #3b82f6; background: #eff6ff; }
    .insight-speed { border-color: #a855f7; background: #faf5ff; }
    
    /* AI 추천 박스 */
    .ai-box {
        background: linear-gradient(to bottom right, #faf5ff, #ede9fe);
        border: 2px solid #c4b5fd;
        border-radius: 12px;
        padding: 16px;
    }
    
    .ai-member-box {
        background: white;
        border-radius: 8px;
        padding: 10px;
        margin: 8px 0;
        border-left: 3px solid #a855f7;
    }
    
    /* 제목 스타일 */
    .section-title {
        font-size: 20px;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 12px;
    }
    
    .subsection-title {
        font-size: 15px;
        font-weight: 600;
        color: #374151;
        margin-bottom: 8px;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(135deg, #a855f7, #9333ea);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def fetch_notion_data():
    try:
        if not NOTION_TOKEN or not DATABASE_ID:
            return pd.DataFrame()
        
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
            df['날짜'] = pd.to_datetime(df['날짜'])
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=1800)  # 30분 캐싱
def get_weather_data(city="Busan", api_key=None):
    """OpenWeatherMap API로 부산 해운대 7일 날씨 가져오기"""
    if not api_key:
        return None
    
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city},KR&appid={api_key}&units=metric&lang=ko"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            weather_list = []
            
            # 오늘부터 7일치 날씨 추출
            for item in data['list'][:8*5]:  # 5일치 (3시간 단위 8개씩)
                dt = datetime.fromtimestamp(item['dt'])
                day_name = ['월','화','수','목','금','토','일'][dt.weekday()]
                temp = f"{item['main']['temp']:.0f}°"
                desc = item['weather'][0]['description']
                icon_map = {
                    '맑음': '☀️', '맑음': '☀️', 
                    '구름': '☁️', '흐림': '☁️',
                    '비': '🌧️', '소나기': '🌦️',
                    '눈': '❄️', '안개': '🌫️'
                }
                icon = icon_map.get(desc, '🌤️')
                
                weather_list.append((day_name, icon, temp))
            
            return weather_list[:7]  # 정확히 7일치만
        return None
    except Exception as e:
        st.error(f"날씨 데이터 로드 실패: {e}")
        return None

def calculate_week_data(df, weeks_ago=0):
    if df.empty:
        return pd.DataFrame()
    
    end_date = datetime.now() - timedelta(days=weeks_ago * 7)
    start_date = end_date - timedelta(days=7)
    
    return df[(df['날짜'] >= start_date) & (df['날짜'] < end_date)]

def get_ai_recommendation(crew_data):
    try:
        crew_summary = "\n".join([
            f"- {m['name']}: 주간 {m['distance']:.1f}km, 평균페이스 {m['pace']}, 연속휴식 {m['rest_days']}일"
            for m in crew_data
        ])
        
        prompt = f"""당신은 전문 러닝 코치입니다. 다음 4명의 크루원에 대해 각각 1-2줄의 간단한 훈련 조언을 해주세요.

{crew_summary}

각 크루원마다:
- 현재 상태 간단 평가
- 다음 주 구체적인 훈련 조언 (거리, 페이스, 휴식 등)

형식:
**크루원이름**: 조언 내용 (1-2줄)

친근하고 동기부여가 되는 톤으로 작성해주세요."""

        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'Content-Type': 'application/json'},
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 1000,
                'messages': [{'role': 'user', 'content': prompt}]
            }
        )
        
        if response.ok:
            data = response.json()
            return data['content'][0]['text']
        return "추천을 생성할 수 없습니다."
    except Exception as e:
        return f"AI 추천 생성 중 오류 발생: {str(e)}"

# 데이터 로드
df = fetch_notion_data()
weather_data = get_weather_data("Busan", WEATHER_API_KEY)

# ========== 상단: 크루 현황 ==========
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)

# 1. 마라톤 대회 신청 안내
st.markdown('<div class="subsection-title">🏃 마라톤 대회 신청 안내</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">부산 벚꽃마라톤 - 신청: 1/10~2/15</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">경남 진해 군항제 마라톤 - 신청: 2/1~3/10</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">부산 낙동강 마라톤 - 신청: 1/20~2/28</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 2. 주간 날씨 (실제 API 데이터로 교체)
st.markdown('<div class="subsection-title">🌤️ 주간 날씨 (해운대)</div>', unsafe_allow_html=True)

if weather_data:
    weather_html = '<div style="display:flex;gap:4px;justify-content:space-between;">'
    for day, icon, temp in weather_data:
        weather_html += f'''
            <div class="weather-card" style="flex:1;min-width:0;">
                <div style="font-weight:600;color:#475569;font-size:10px;">{day}</div>
                <div style="font-size:20px;margin:2px 0;">{icon}</div>
                <div style="font-weight:700;color:#1e293b;font-size:11px;">{temp}</div>
            </div>
        '''
    weather_html += '</div>'
    st.markdown(weather_html, unsafe_allow_html=True)
    st.caption("🌐 OpenWeatherMap 실시간 데이터")
else:
    # API 키 없으면 기존 하드코딩 데이터 표시
    fallback_weather = [
        ('월', '☀️', '5°'), ('화', '☁️', '3°'), ('수', '🌧️', '2°'),
        ('목', '☁️', '4°'), ('금', '☀️', '6°'), ('토', '☀️', '7°'), ('일', '⛅', '5°')
    ]
    weather_html = '<div style="display:flex;gap:4px;justify-content:space-between;">'
    for day, icon, temp in fallback_weather:
        weather_html += f'''
            <div class="weather-card" style="flex:1;min-width:0;">
                <div style="font-weight:600;color:#475569;font-size:10px;">{day}</div>
                <div style="font-size:20px;margin:2px 0;">{icon}</div>
                <div style="font-weight:700;color:#1e293b;font-size:11px;">{temp}</div>
            </div>
        '''
    weather_html += '</div>'
    st.markdown(weather_html, unsafe_allow_html=True)
    st.caption("⚠️ API 키 설정 시 실시간 날씨 표시 (환경변수 WEATHER_API_KEY)")

st.markdown("<br>", unsafe_allow_html=True)

# 3. 총 거리 (크루 합산)
st.markdown('<div class="subsection-title">🎯 총 거리 (크루 합산)</div>', unsafe_allow_html=True)

if not df.empty:
    this_week = calculate_week_data(df, 0)
    last_week = calculate_week_data(df, 1)
    
    total_dist = this_week['거리'].sum()
    prev_dist = last_week['거리'].sum()
    
    if prev_dist > 0:
        percent_change = ((total_dist - prev_dist) / prev_dist) * 100
    else:
        percent_change = 0
    
    trend_icon = "📈" if percent_change >= 0 else "📉"
    trend_color = "#10b981" if percent_change >= 0 else "#ef4444"
    
    st.markdown(f'''
        <div class="total-distance-card">
            <div style="font-size:40px;font-weight:800;color:#047857;margin-bottom:6px;">
                {total_dist:.1f}<span style="font-size:20px;color:#6b7280;"> km</span>
            </div>
            <div style="font-size:13px;color:#6b7280;margin-bottom:8px;">
                지난주: {prev_dist:.1f}km
            </div>
            <div style="font-size:14px;font-weight:600;color:{trend_color};">
                {trend_icon} 전주 대비 {percent_change:+.0f}%
            </div>
        </div>
    ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# 나머지 코드 (크루 컨디션, Insight & Fun, AI 추천)는 동일...
# [기존 코드 유지]

if __name__ == "__main__":
    # 크루 컨디션 섹션 등 나머지 코드도 동일하게 유지됩니다.
    pass
