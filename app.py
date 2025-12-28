import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 개선 (사진 및 카드 디자인 최적화)
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
    .crew-photo {
        width: 80px; height: 80px; border-radius: 50%;
        margin: 0 auto 10px; object-fit: cover;
        border: 3px solid #3b82f6; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        display: block;
    }
    .crew-avatar {
        width: 80px; height: 80px; border-radius: 50%;
        background: #e5e7eb; margin: 0 auto 10px;
        display: flex; align-items: center; justify-content: center;
        font-size: 32px; border: 3px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    .crew-stat-box {
        background: #f3f4f6; border-radius: 6px; padding: 8px 4px;
        margin: 4px 0; font-size: 12px; text-align: center;
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
    }
    .section-title { font-size: 20px; font-weight: 700; color: #1f2937; margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)

# 3. 데이터 로드 및 파싱 (에러 해결 포인트)
@st.cache_data(ttl=600) # 사진 만료 방지를 위해 TTL 설정
def fetch_notion_data():
    try:
        response = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            json={}
        )
        if not response.ok: return pd.DataFrame()
        
        results = response.json().get("results", [])
        data = []
        
        for row in results:
            props = row.get("properties", {})
            
            # 날짜 파싱
            date_val = None
            if props.get("날짜", {}).get("date"):
                date_val = props["날짜"]["date"]["start"][:10]
            
            # 러너 파싱
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            # 거리 파싱
            dist = 0
            for col in ["실제 거리", "거리"]:
                if props.get(col, {}).get("number") is not None:
                    dist = props[col]["number"]
                    if dist > 100: dist /= 1000 # m단위일 경우 km로 변환
                    break
            
            # 페이스 파싱 (가장 중요한 부분)
            pace = "N/A"
            for col in ["평균 페이스", "페이스", "Pace"]:
                p_prop = props.get(col, {})
                if p_prop.get("type") == "number" and p_prop.get("number"):
                    sec = p_prop["number"]
                    pace = f"{int(sec//60)}:{int(sec%60):02d}"
                    break
                elif p_prop.get("type") == "rich_text" and p_prop.get("rich_text"):
                    pace = p_prop["rich_text"][0]["plain_text"]
                    break
            
            # 고도 파싱
            elev = props.get("고도", {}).get("number", 0) or 0
            
            # 사진 파싱 (URL 만료 이슈 대응)
            photo_url = None
            if props.get("사진", {}).get("files"):
                files = props["사진"]["files"]
                if files:
                    file_obj = files[0]
                    photo_url = file_obj.get("file", {}).get("url") or file_obj.get("external", {}).get("url")
            
            data.append({
                "날짜": date_val, "러너": runner, "거리": dist,
                "고도": elev, "페이스": pace, "사진": photo_url
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            df = df.dropna(subset=['날짜'])
        return df
    except Exception as e:
        st.error(f"데이터 로드 에러: {e}")
        return pd.DataFrame()

# 페이스 계산 헬퍼
def pace_to_seconds(pace_str):
    if not pace_str or pace_str == "N/A" or ":" not in str(pace_str):
        return 9999
    try:
        m, s = map(int, str(pace_str).split(':'))
        return m * 60 + s
    except:
        return 9999

def calculate_rest_days(member_data):
    if member_data.empty: return 0
    sorted_dates = sorted(member_data['날짜'].dt.date.unique(), reverse=True)
    today = datetime.now().date()
    rest = 0
    for i in range(30):
        check_date = today - timedelta(days=i)
        if check_date not in sorted_dates: rest += 1
        else: break
    return rest

# --- 메인 렌더링 ---
df = fetch_notion_data()

if not df.empty:
    st.title("🏃 러닝 크루 대시보드")
    
    # [섹션 1] 크루 현황
    tw = df[df['날짜'] >= (datetime.now() - timedelta(days=7))]
    lw = df[(df['날짜'] < (datetime.now() - timedelta(days=7))) & (df['날짜'] >= (datetime.now() - timedelta(days=14)))]
    
    total_dist = tw['거리'].sum()
    prev_dist = lw['거리'].sum()
    p_change = ((total_dist - prev_dist) / prev_dist * 100) if prev_dist > 0 else 0
    
    st.markdown(f'''
        <div class="section-card">
            <div class="section-title">📊 크루 현황</div>
            <div class="total-distance-card">
                <div style="font-size:14px;color:#059669;font-weight:600;">총 거리 (크루 합산)</div>
                <div style="font-size:42px;font-weight:800;color:#047857;">{total_dist:.1f} km</div>
                <div style="font-size:14px;color:#6b7280;">지난주 대비 {p_change:+.1f}%</div>
            </div>
        </div>
    ''', unsafe_allow_html=True)

    # [섹션 2] 크루 컨디션
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)
    
    crew_members = df['러너'].unique()
    cols = st.columns(len(crew_members[:4]))
    
    for idx, member in enumerate(crew_members[:4]):
        m_data = df[df['러너'] == member]
        tw_m = m_data[m_data['날짜'] >= (datetime.now() - timedelta(days=7))]
        
        w_dist = tw_m['거리'].sum()
        # 평균 페이스: 이번 주 데이터 중 가장 최근 것
        avg_pace = tw_m.sort_values('날짜', ascending=False)['페이스'].iloc[0] if not tw_m.empty else "N/A"
        rest_days = calculate_rest_days(m_data)
        photo = m_data.sort_values('날짜', ascending=False)['사진'].dropna().iloc[0] if not m_data['사진'].dropna().empty else None
        
        with cols[idx]:
            if photo:
                st.markdown(f'<img src="{photo}" class="crew-photo">', unsafe_allow_html=True)
            else:
                st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="crew-stat-box" style="background:#dbeafe;"><div class="stat-label">주간 거리</div><div class="stat-value">{w_dist:.1f}km</div></div>
            <div class="crew-stat-box" style="background:#f3e8ff;"><div class="stat-label">평균 페이스</div><div class="stat-value">{avg_pace}</div></div>
            <div class="crew-stat-box" style="background:#fef3c7;"><div class="stat-label">연속 휴식</div><div class="stat-value">{rest_days}일</div></div>
            """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # [섹션 3] Insights & Fun (정렬 로직 수정)
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🏆 Insights & Fun</div>', unsafe_allow_html=True)
    
    if not tw.empty:
        # 최장 거리
        dist_rank = tw.groupby('러너')['거리'].sum()
        st.markdown(f'<div class="insight-box insight-distance">🥇 최장 거리 주자: <b>{dist_rank.idxmax()} ({dist_rank.max():.1f}km)</b></div>', unsafe_allow_html=True)
        
        # 최고 속도 (페이스가 가장 낮은 사람)
        tw['pace_sec'] = tw['페이스'].apply(pace_to_seconds)
        fast_runners = tw[tw['pace_sec'] < 9999]
        if not fast_runners.empty:
            fastest = fast_runners.loc[fast_runners['pace_sec'].idxmin()]
            st.markdown(f'<div class="insight-box insight-pace">⚡ 최고 스피드 러너: <b>{fastest["러너"]} ({fastest["페이스"]}/km)</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.error("데이터를 가져오지 못했습니다. 노션 설정을 확인해주세요.")
