import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta

# 1. 설정: GitHub/Streamlit Secrets에서 불러옴
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

# 페이지 설정
st.set_page_config(page_title="러닝 대시보드", layout="wide")

# CSS 스타일링 (이미지의 디자인을 최대한 구현)
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .crew-card {
        background-color: white;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-top: 5px solid #4e73df;
    }
    .crew-img { border-radius: 50%; width: 80px; height: 80px; object-fit: cover; margin-bottom: 10px; }
    .insight-box {
        background-color: #fffde7;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #fbc02d;
    }
    </style>
    """, unsafe_allow_html=True)

def fetch_data():
    try:
        if not NOTION_TOKEN or not DATABASE_ID:
            return pd.DataFrame()
        
        notion = Client(auth=NOTION_TOKEN)
        response = notion.databases.query(database_id=DATABASE_ID)
        results = response.get("results", [])
        data = []
        
        for row in results:
            props = row.get("properties", {})
            # 필드 추출 (노션 컬럼명과 일치해야 함)
            date_val = props.get("날짜", {}).get("date", {}).get("start", "")[:10] if props.get("날짜", {}).get("date") else ""
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            # 숫자 데이터 추출 로직
            dist = 0
            for k, v in props.items():
                if "거리" in k and v.get("number") is not None: dist = v["number"]
            elev = 0
            for k, v in props.items():
                if "고도" in k and v.get("number") is not None: elev = v["number"]
            
            data.append({"날짜": date_val, "러너": runner, "거리": dist, "고도": elev})
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'])
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

# 데이터 처리
df = fetch_data()

# ----------------- 상단: 크루 현황 -----------------
st.title("🏃‍♂️ 우리 크루 실시간 훈련 현황")

col_top1, col_top2 = st.columns([2, 1])

with col_top1:
    st.subheader("📋 공지사항")
    st.info("🏃‍♂️ 벚꽃 마라톤 신청: 1/10 ~ 2/15 | ⛰️ 주말 산악 훈련 예정")
    
    st.subheader("🌤️ 주간 일기예보")
    # 실제 날씨 API 연결 전 임시 표시
    cols = st.columns(7)
    days = ["월", "화", "수", "목", "금", "토", "일"]
    for i, col in enumerate(cols):
        col.write(days[i])
        col.write("☀️")

with col_top2:
    if not df.empty:
        # 이번 주 데이터 필터링
        this_week = df[df['날짜'] >= (datetime.now() - timedelta(days=7))]
        last_week = df[(df['날짜'] < (datetime.now() - timedelta(days=7))) & (df['날짜'] >= (datetime.now() - timedelta(days=14)))]
        
        total_dist = this_week['거리'].sum()
        prev_dist = last_week['거리'].sum()
        delta = total_dist - prev_dist
        
        st.metric("🏃‍♂️ 총 거리 (크루 합산)", f"{total_dist:.1f} km", delta=f"{delta:+.1f} km")

st.divider()

# ----------------- 중단: 크루 컨디션 (그리드) -----------------
st.subheader("👥 크루 컨디션")
if not df.empty:
    crew_members = ["용남", "주현", "민수", "서훈"] # 실제 노션의 '러너' 이름과 맞추세요
    cols = st.columns(4)
    
    for i, member in enumerate(crew_members):
        with cols[i]:
            member_data = df[df['러너'] == member]
            week_dist = member_data[member_data['날짜'] >= (datetime.now() - timedelta(days=7))]['거리'].sum()
            # 여기에 실제 사진 URL이 있다면 넣을 수 있습니다. 지금은 임시 아이콘.
            st.markdown(f"""
                <div class="crew-card">
                    <img src="https://via.placeholder.com/80" class="crew-img">
                    <h4>{member}</h4>
                    <p><b>주간 거리:</b> {week_dist:.1f} km</p>
                    <p style="font-size: 0.8em; color: gray;">연속 휴식: 2일</p>
                </div>
            """, unsafe_allow_html=True)

st.divider()

# ----------------- 하단: Insight & Fun -----------------
st.subheader("💡 Insight & Fun")
if not df.empty:
    col_fun1, col_fun2, col_fun3 = st.columns(3)
    
    # 1. 사실상 Full (20km 이상)
    full_runners = df[(df['거리'] >= 20) & (df['날짜'] >= (datetime.now() - timedelta(days=7)))]
    with col_fun1:
        st.markdown("**🏃‍♂️ 사실상 Full (주간 20k+)**")
        for _, r in full_runners.iterrows():
            st.write(f"- {r['러너']} ({r['거리']}k, {r['날짜'].strftime('%m/%d')})")
            
    # 2. 사실상 등산 (최고 고도)
    top_elev = df[df['날짜'] >= (datetime.now() - timedelta(days=7))].sort_values(by="고도", ascending=False).head(1)
    with col_fun2:
        st.markdown("**⛰️ 사실상 등산 (최고 고도)**")
        if not top_elev.empty:
            st.write(f"- {top_elev.iloc[0]['러너']} ({top_elev.iloc[0]['고도']}m, {top_elev.iloc[0]['날짜'].strftime('%m/%d')})")

    # 3. 우사인 볼트 (이 부분은 페이스 데이터가 노션에 있을 경우 추가 가능)
    with col_fun3:
        st.markdown("**⚡ 사실상 우사인 볼트**")
        st.write("- 데이터 준비 중 (페이스)")
