import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정 (Streamlit Secrets 또는 OS 환경변수)
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

# 페이지 기본 설정
st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. 모바일 최적화 CSS
st.markdown("""
<style>
    .main { background-color: #f9fafb; padding: 10px; }
    .section-card {
        background: white; border-radius: 12px; padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px;
    }
    .notice-box {
        background: #eff6ff; border: 2px solid #bfdbfe; border-radius: 8px;
        padding: 10px; margin-bottom: 6px; font-size: 13px; color: #1e40af;
    }
    .total-distance-card {
        background: linear-gradient(to bottom right, #ecfdf5, #d1fae5);
        border: 2px solid #86efac; border-radius: 12px; padding: 16px; text-align: center;
    }
    .crew-card {
        background: white; border: 2px solid #e5e7eb; border-radius: 10px;
        padding: 10px 8px; text-align: center; height: 100%;
    }
    .crew-avatar {
        width: 60px; height: 60px; border-radius: 50%;
        background: linear-gradient(135deg, #3b82f6, #60a5fa);
        margin: 0 auto 8px; display: flex; align-items: center; justify-content: center;
        font-size: 28px; border: 3px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    .crew-stat-box {
        background: #f3f4f6; border-radius: 4px; padding: 6px 4px;
        margin: 3px 0; font-size: 11px;
    }
    .insight-box {
        background: white; border-left: 4px solid; border-radius: 8px;
        padding: 12px; margin: 6px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .insight-full { border-color: #10b981; background: #f0fdf4; }
    .ai-box {
        background: linear-gradient(to bottom right, #faf5ff, #ede9fe);
        border: 2px solid #c4b5fd; border-radius: 12px; padding: 16px;
    }
    .section-title { font-size: 20px; font-weight: 700; color: #1f2937; margin-bottom: 12px; }
    .subsection-title { font-size: 15px; font-weight: 600; color: #374151; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# 3. 데이터 로드 함수 (수정된 버전)
@st.cache_data(ttl=300)
def fetch_notion_data():
    try:
        if not NOTION_TOKEN or not DATABASE_ID:
            st.error("설정 오류: 토큰 또는 데이터베이스 ID가 없습니다.")
            return pd.DataFrame()
        
        # 클라이언트 선언
        notion = Client(auth=NOTION_TOKEN)
        
        # [핵심 수정] query 메서드를 직접 호출하지 않고 올바른 방식 사용
        try:
            # 방법 1: 최신 버전 (2.0.0+)
            response = notion.databases.query(database_id=DATABASE_ID)
        except AttributeError:
            # 방법 2: 구버전 호환
            response = notion.databases.query(**{"database_id": DATABASE_ID})
        
        results = response.get("results", [])
        
        if not results:
            st.warning("데이터베이스에 데이터가 없습니다.")
            return pd.DataFrame()
        
        data = []
        
        for row in results:
            props = row.get("properties", {})
            
            # 날짜 파싱
            date_val = ""
            date_prop = props.get("날짜", {})
            if date_prop.get("type") == "date" and date_prop.get("date"):
                date_val = date_prop["date"].get("start", "")[:10]
            
            # 러너 이름
            runner_prop = props.get("러너", {})
            runner = "Unknown"
            if runner_prop.get("type") == "select" and runner_prop.get("select"):
                runner = runner_prop["select"].get("name", "Unknown")
            
            dist, elev, pace, photo_url = 0, 0, None, None
            
            # 각 속성 파싱
            for k, v in props.items():
                prop_type = v.get("type", "")
                
                # 거리
                if "거리" in k and prop_type == "number" and v.get("number") is not None:
                    dist = v["number"] / 1000 if v["number"] > 100 else v["number"]
                
                # 고도
                if "고도" in k and prop_type == "number" and v.get("number") is not None:
                    elev = v["number"]
                
                # 페이스
                if ("페이스" in k or "pace" in k.lower()) and prop_type == "rich_text":
                    if v.get("rich_text") and len(v["rich_text"]) > 0:
                        pace = v["rich_text"][0].get("plain_text", "")
                
                # 사진
                if ("사진" in k or "photo" in k.lower() or "이미지" in k or "image" in k.lower()) and prop_type == "files":
                    if v.get("files") and len(v["files"]) > 0:
                        file_obj = v["files"][0]
                        photo_url = file_obj.get("file", {}).get("url") or file_obj.get("external", {}).get("url")
            
            data.append({
                "날짜": date_val, "러너": runner, "거리": dist,
                "고도": elev, "페이스": pace, "사진": photo_url
            })
        
        df = pd.DataFrame(data)
        if not df.empty and '날짜' in df.columns:
            df = df[df['날짜'] != ""]  # 빈 날짜 제거
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            df = df.dropna(subset=['날짜'])  # 날짜 파싱 실패한 행 제거
        
        return df
        
    except Exception as e:
        st.error(f"데이터 로드 실패: {str(e)}")
        st.exception(e)  # 디버깅용 상세 에러 출력
        return pd.DataFrame()

# 4. 헬퍼 함수
def calculate_week_data(df, weeks_ago=0):
    if df.empty: 
        return pd.DataFrame()
    end_date = datetime.now() - timedelta(days=weeks_ago * 7)
    start_date = end_date - timedelta(days=7)
    return df[(df['날짜'] >= start_date) & (df['날짜'] < end_date)]

def get_ai_recommendation(crew_data):
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return "API 키가 설정되지 않았습니다."
        
        crew_summary = "\n".join([f"- {m['name']}: {m['distance']:.1f}km, 페이스 {m['pace']}" for m in crew_data])
        prompt = f"당신은 전문 러닝 코치입니다. 다음 크루원들에게 1-2줄의 조언을 해주세요.\n\n{crew_summary}"
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 500,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=10
        )
        
        if response.ok:
            return response.json()['content'][0]['text']
        else:
            return f"AI 조언을 가져올 수 없습니다. (상태: {response.status_code})"
    except Exception as e:
        return f"추천 생성 오류: {str(e)}"

# --- 앱 실행 ---
st.title("🏃 러닝 크루 대시보드")

# 데이터 로드
df = fetch_notion_data()

if df.empty:
    st.warning("데이터를 불러올 수 없습니다. Notion 연동 설정을 확인해주세요.")
    st.info("필요한 환경 변수: NOTION_TOKEN, DATABASE_ID")
    st.stop()

# [섹션 1] 크루 현황
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)

st.markdown('<div class="subsection-title">🏃 마라톤 대회 안내</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">부산 벚꽃마라톤 (1/10~2/15)</div>', unsafe_allow_html=True)
st.markdown('<div class="notice-box">경남 진해 군항제 마라톤 (2/1~3/10)</div>', unsafe_allow_html=True)

tw = calculate_week_data(df, 0)
lw = calculate_week_data(df, 1)
total_dist = tw['거리'].sum()
prev_dist = lw['거리'].sum()
p_change = ((total_dist - prev_dist) / prev_dist * 100) if prev_dist > 0 else 0

st.markdown(f'''
    <div class="total-distance-card">
        <div style="font-size:36px;font-weight:800;color:#047857;">{total_dist:.1f} km</div>
        <div style="font-size:13px;color:#6b7280;">지난주 대비 {p_change:+.0f}%</div>
    </div>
''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# [섹션 2] 크루 컨디션
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)

crew_members = df['러너'].unique()[:4]
cols = st.columns(min(4, len(crew_members)))
crew_data_ai = []

for idx, member in enumerate(crew_members):
    if idx < len(cols):
        with cols[idx]:
            m_data = df[df['러너'] == member]
            tw_m = calculate_week_data(m_data, 0)
            w_dist = tw_m['거리'].sum()
            avg_p = tw_m['페이스'].dropna().iloc[0] if not tw_m.empty and not tw_m['페이스'].dropna().empty else "5:30"
            
            crew_data_ai.append({'name': member, 'distance': w_dist, 'pace': avg_p})
            
            st.markdown(f"""
            <div class="crew-card">
                <div class="crew-avatar">👤</div>
                <h3 style="font-size:14px; margin:5px 0;">{member}</h3>
                <div class="crew-stat-box" style="background:#dbeafe;">{w_dist:.1f}km</div>
                <div class="crew-stat-box" style="background:#f3e8ff;">{avg_p}</div>
            </div>
            """, unsafe_allow_html=True)

st.session_state['crew_data_for_ai'] = crew_data_ai
st.markdown('</div>', unsafe_allow_html=True)

# [섹션 3] AI 코치
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🤖 AI 코치</div>', unsafe_allow_html=True)

if st.button("✨ AI 코치 조언 듣기"):
    if 'crew_data_for_ai' in st.session_state and st.session_state['crew_data_for_ai']:
        with st.spinner("분석 중..."):
            st.session_state['ai_res'] = get_ai_recommendation(st.session_state['crew_data_for_ai'])

if 'ai_res' in st.session_state:
    st.markdown(f'<div class="ai-box">{st.session_state["ai_res"]}</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
