import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# 페이지 설정
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
        padding: 12px; text-align: center; height: 100%;
    }
    .crew-photo {
        width: 80px; height: 80px; border-radius: 50%;
        margin: 0 auto 10px; object-fit: cover;
        border: 3px solid #3b82f6; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    .crew-avatar {
        width: 80px; height: 80px; border-radius: 50%;
        background: linear-gradient(135deg, #3b82f6, #60a5fa);
        margin: 0 auto 10px; display: flex; align-items: center; justify-content: center;
        font-size: 32px; border: 3px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    .crew-stat-box {
        background: #f3f4f6; border-radius: 6px; padding: 8px 4px;
        margin: 4px 0; font-size: 12px;
    }
    .stat-label { font-size: 10px; color: #6b7280; font-weight: 600; }
    .stat-value { font-size: 15px; font-weight: 700; color: #1f2937; }
    .insight-box {
        background: white; border-left: 4px solid; border-radius: 8px;
        padding: 12px; margin: 8px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .insight-distance { border-color: #f59e0b; background: #fffbeb; }
    .insight-elevation { border-color: #8b5cf6; background: #faf5ff; }
    .insight-pace { border-color: #10b981; background: #f0fdf4; }
    .ai-box {
        background: linear-gradient(to bottom right, #faf5ff, #ede9fe);
        border: 2px solid #c4b5fd; border-radius: 12px; padding: 16px;
        font-size: 14px; line-height: 1.6;
    }
    .section-title { font-size: 20px; font-weight: 700; color: #1f2937; margin-bottom: 12px; }
    .subsection-title { font-size: 15px; font-weight: 600; color: #374151; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# 3. 데이터 로드 함수 (requests 직접 사용)
@st.cache_data(ttl=300)
def fetch_notion_data():
    try:
        if not NOTION_TOKEN or not DATABASE_ID:
            st.error("설정 오류: 토큰 또는 데이터베이스 ID가 없습니다.")
            return pd.DataFrame()
        
        # requests로 직접 Notion API 호출
        response = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            json={}
        )
        
        if not response.ok:
            st.error(f"API 호출 실패: {response.status_code}")
            return pd.DataFrame()
        
        results = response.json().get("results", [])
        
        if not results:
            st.warning("데이터베이스에 데이터가 없습니다.")
            return pd.DataFrame()
        
        data = []
        
        for row in results:
            props = row.get("properties", {})
            
            # 날짜
            date_val = ""
            date_prop = props.get("날짜", {})
            if date_prop.get("type") == "date" and date_prop.get("date"):
                date_val = date_prop["date"].get("start", "")[:10]
            
            # 러너 (Select 타입)
            runner_prop = props.get("러너", {})
            runner = "Unknown"
            if runner_prop.get("type") == "select" and runner_prop.get("select"):
                runner = runner_prop["select"].get("name", "Unknown")
            
            # 거리 (실제 거리 또는 거리 컬럼 사용)
            dist = 0
            if props.get("실제 거리", {}).get("type") == "number":
                dist_val = props["실제 거리"].get("number", 0)
                dist = dist_val / 1000 if dist_val and dist_val > 100 else (dist_val or 0)
            elif props.get("거리", {}).get("type") == "number":
                dist_val = props["거리"].get("number", 0)
                dist = dist_val / 1000 if dist_val and dist_val > 100 else (dist_val or 0)
            
            # 고도
            elev = 0
            if props.get("고도", {}).get("type") == "number":
                elev = props["고도"].get("number", 0) or 0
            
            # 페이스 (평균 페이스 또는 평균 페이스 컬럼)
            pace = None
            if props.get("평균 페이스", {}).get("type") == "number":
                pace_sec = props["평균 페이스"].get("number")
                if pace_sec:
                    minutes = int(pace_sec // 60)
                    seconds = int(pace_sec % 60)
                    pace = f"{minutes}:{seconds:02d}"
            elif props.get("평균 페이스", {}).get("type") == "rich_text":
                pace_text = props["평균 페이스"].get("rich_text", [])
                if pace_text:
                    pace = pace_text[0].get("plain_text", "")
            
            # 사진 (Files 타입)
            photo_url = None
            if props.get("사진", {}).get("type") == "files":
                files = props["사진"].get("files", [])
                if files and len(files) > 0:
                    file_obj = files[0]
                    photo_url = file_obj.get("file", {}).get("url") or file_obj.get("external", {}).get("url")
            
            data.append({
                "날짜": date_val, "러너": runner, "거리": dist,
                "고도": elev, "페이스": pace, "사진": photo_url
            })
        
        df = pd.DataFrame(data)
        if not df.empty and '날짜' in df.columns:
            df = df[df['날짜'] != ""]
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            df = df.dropna(subset=['날짜'])
        
        return df
        
    except Exception as e:
        st.error(f"데이터 로드 실패: {str(e)}")
        return pd.DataFrame()

# 4. 헬퍼 함수들
def calculate_week_data(df, weeks_ago=0):
    if df.empty: 
        return pd.DataFrame()
    end_date = datetime.now() - timedelta(days=weeks_ago * 7)
    start_date = end_date - timedelta(days=7)
    return df[(df['날짜'] >= start_date) & (df['날짜'] < end_date)]

def calculate_rest_days(member_data):
    """연속 휴식일 계산"""
    if member_data.empty:
        return 0
    
    sorted_data = member_data.sort_values('날짜', ascending=False)
    today = datetime.now().date()
    rest_days = 0
    
    for i in range(30):  # 최근 30일 체크
        check_date = today - timedelta(days=i)
        if check_date not in sorted_data['날짜'].dt.date.values:
            rest_days += 1
        else:
            break
    
    return rest_days

def pace_to_seconds(pace_str):
    """페이스 문자열을 초로 변환"""
    try:
        if not pace_str or pace_str == "":
            return 999999
        parts = pace_str.strip().split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return 999999
    except:
        return 999999

def get_ai_coaching(crew_summary, total_dist, prev_dist):
    """실제 AI 코칭 조언"""
    try:
        if not ANTHROPIC_API_KEY:
            return "❌ ANTHROPIC_API_KEY가 설정되지 않았습니다."
        
        prompt = f"""당신은 전문 러닝 코치입니다. 다음 러닝 크루의 지난주 실적을 분석하고, 이번 주 훈련에 도움이 될 구체적인 조언을 3-4문장으로 제공해주세요.

**지난주 크루 실적:**
- 총 거리: {total_dist:.1f}km (전주 대비: {((total_dist - prev_dist) / prev_dist * 100) if prev_dist > 0 else 0:+.1f}%)

**크루원별 상세:**
{crew_summary}

**조언 시 고려사항:**
- 각 크루원의 거리, 페이스, 휴식일을 고려
- 부상 예방과 점진적 향상에 중점
- 구체적이고 실천 가능한 조언
- 긍정적이고 동기부여가 되는 톤

이번 주 훈련 조언:"""

        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 800,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=15
        )
        
        if response.ok:
            return response.json()['content'][0]['text']
        else:
            return f"❌ AI 조언을 가져올 수 없습니다. (상태 코드: {response.status_code})"
            
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"

# --- 메인 앱 ---
st.title("🏃 러닝 크루 대시보드")

df = fetch_notion_data()

if df.empty:
    st.warning("⚠️ 데이터를 불러올 수 없습니다. Notion 연동 설정을 확인해주세요.")
    st.info("📌 필요한 환경 변수: NOTION_TOKEN, DATABASE_ID")
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
        <div style="font-size:14px;color:#059669;font-weight:600;margin-bottom:8px;">총 거리 (크루 합산)</div>
        <div style="font-size:42px;font-weight:800;color:#047857;">{total_dist:.1f} km</div>
        <div style="font-size:14px;color:#6b7280;margin-top:4px;">지난주 대비 {p_change:+.1f}%</div>
    </div>
''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# [섹션 2] 크루 컨디션
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)

crew_members = df['러너'].unique()
cols = st.columns(min(4, len(crew_members)))
crew_data_for_ai = []

for idx, member in enumerate(crew_members[:4]):
    with cols[idx]:
        m_data = df[df['러너'] == member]
        tw_m = calculate_week_data(m_data, 0)
        lw_m = calculate_week_data(m_data, 1)
        
        w_dist = tw_m['거리'].sum()
        prev_w_dist = lw_m['거리'].sum()
        w_change = ((w_dist - prev_w_dist) / prev_w_dist * 100) if prev_w_dist > 0 else 0
        
        avg_pace = "N/A"
        if not tw_m.empty and not tw_m['페이스'].dropna().empty:
            avg_pace = tw_m['페이스'].dropna().iloc[0]
        
        rest_days = calculate_rest_days(m_data)
        
        # 사진 가져오기
        photo = None
        if not tw_m.empty:
            recent_photos = tw_m['사진'].dropna()
            if not recent_photos.empty:
                photo = recent_photos.iloc[0]
        
        crew_data_for_ai.append({
            'name': member,
            'distance': w_dist,
            'pace': avg_pace,
            'rest_days': rest_days,
            'change': w_change
        })
        
        # 카드 렌더링
        if photo:
            st.markdown(f'<img src="{photo}" class="crew-photo">', unsafe_allow_html=True)
        else:
            st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
        
        st.markdown(f'<h3 style="font-size:16px; margin:8px 0; font-weight:700;">{member}</h3>', unsafe_allow_html=True)
        
        st.markdown(f'''
            <div class="crew-stat-box" style="background:#dbeafe;">
                <div class="stat-label">주간 거리</div>
                <div class="stat-value">{w_dist:.1f} km</div>
            </div>
        ''', unsafe_allow_html=True)
        
        st.markdown(f'''
            <div class="crew-stat-box" style="background:#dcfce7;">
                <div class="stat-label">전주 대비</div>
                <div class="stat-value" style="color:{'#dc2626' if w_change < 0 else '#16a34a'};">{w_change:+.1f}%</div>
            </div>
        ''', unsafe_allow_html=True)
        
        st.markdown(f'''
            <div class="crew-stat-box" style="background:#f3e8ff;">
                <div class="stat-label">평균 속도</div>
                <div class="stat-value">{avg_pace}</div>
            </div>
        ''', unsafe_allow_html=True)
        
        st.markdown(f'''
            <div class="crew-stat-box" style="background:#fef3c7;">
                <div class="stat-label">연속 휴식일</div>
                <div class="stat-value" style="color:{'#dc2626' if rest_days > 3 else '#16a34a'};">{rest_days}일</div>
            </div>
        ''', unsafe_allow_html=True)

st.session_state['crew_data_for_ai'] = crew_data_for_ai
st.session_state['total_dist'] = total_dist
st.session_state['prev_dist'] = prev_dist
st.markdown('</div>', unsafe_allow_html=True)

# [섹션 3] Insights & Fun
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🏆 Insights & Fun</div>', unsafe_allow_html=True)

if not tw.empty:
    # 가장 긴 거리
    top_runner = tw.groupby('러너')['거리'].sum().idxmax()
    top_dist = tw.groupby('러너')['거리'].sum().max()
    
    st.markdown(f'''
        <div class="insight-box insight-distance">
            <div style="font-size:13px;font-weight:600;color:#92400e;margin-bottom:4px;">🥇 최장 거리 주자</div>
            <div style="font-size:16px;font-weight:700;color:#78350f;">{top_runner} - {top_dist:.1f}km</div>
        </div>
    ''', unsafe_allow_html=True)
    
    # 가장 높은 고도
    if tw['고도'].sum() > 0:
        top_climber = tw.groupby('러너')['고도'].sum().idxmax()
        top_elev = tw.groupby('러너')['고도'].sum().max()
        
        st.markdown(f'''
            <div class="insight-box insight-elevation">
                <div style="font-size:13px;font-weight:600;color:#5b21b6;margin-bottom:4px;">⛰️ 최고 고도 정복자</div>
                <div style="font-size:16px;font-weight:700;color:#4c1d95;">{top_climber} - {top_elev:.0f}m</div>
            </div>
        ''', unsafe_allow_html=True)
    
    # 가장 빠른 페이스
    tw_pace = tw[tw['페이스'].notna()].copy()
    if not tw_pace.empty:
        tw_pace['페이스_초'] = tw_pace['페이스'].apply(pace_to_seconds)
        fastest_idx = tw_pace['페이스_초'].idxmin()
        fastest_runner = tw_pace.loc[fastest_idx, '러너']
        fastest_pace = tw_pace.loc[fastest_idx, '페이스']
        
        st.markdown(f'''
            <div class="insight-box insight-pace">
                <div style="font-size:13px;font-weight:600;color:#065f46;margin-bottom:4px;">⚡ 최고 스피드 러너</div>
                <div style="font-size:16px;font-weight:700;color:#064e3b;">{fastest_runner} - {fastest_pace}/km</div>
            </div>
        ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# [섹션 4] AI 코치
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🤖 AI 러닝 코치</div>', unsafe_allow_html=True)

if st.button("✨ 이번 주 훈련 조언 받기", type="primary"):
    if 'crew_data_for_ai' in st.session_state:
        with st.spinner("🏃 AI 코치가 분석 중입니다..."):
            crew_summary = "\n".join([
                f"- {m['name']}: {m['distance']:.1f}km, 페이스 {m['pace']}, 휴식 {m['rest_days']}일, 전주대비 {m['change']:+.1f}%"
                for m in st.session_state['crew_data_for_ai']
            ])
            
            ai_advice = get_ai_coaching(
                crew_summary,
                st.session_state['total_dist'],
                st.session_state['prev_dist']
            )
            st.session_state['ai_advice'] = ai_advice

if 'ai_advice' in st.session_state:
    st.markdown(f'<div class="ai-box">{st.session_state["ai_advice"]}</div>', unsafe_allow_html=True)
else:
    st.info("👆 버튼을 눌러 AI 코치의 맞춤 훈련 조언을 받아보세요!")

st.markdown('</div>', unsafe_allow_html=True)
