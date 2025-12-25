import streamlit as st
from notion_client import Client
import pandas as pd

# 1. 설정
NOTION_TOKEN = "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"
DATABASE_ID = "2d18ddf6369c8077a12ad817fde87b5b"

def fetch_data():
    notion = Client(auth=NOTION_TOKEN)
    response = notion.databases.query(**{"database_id": DATABASE_ID})
    results = response.get("results", [])
    data = []
    
    for row in results:
        props = row.get("properties", {})
        # 노션의 실제 컬럼명에 맞춰 안전하게 추출
        try:
            name = props.get("이름", {}).get("title", [{}])[0].get("plain_text", "무명")
            date = props.get("날짜", {}).get("date", {}).get("start", "")[:10] if props.get("날짜", {}).get("date") else ""
            runner = props.get("러너", {}).get("select", {}).get("name", "미정") if props.get("러너", {}).get("select") else "미정"
            
            # '실제 거리' 또는 '거리' 컬럼 확인
            dist = props.get("실제 거리", {}).get("number", 0) or props.get("거리", {}).get("number", 0) or 0
            elev = props.get("고도", {}).get("number", 0) or 0
            
            data.append({"이름": name, "날짜": date, "러너": runner, "거리(km)": dist, "고도(m)": elev})
        except:
            continue
    return pd.DataFrame(data)

# 2. 화면 꾸미기 (선생님이 원하셨던 프로토타입 스타일)
st.set_page_config(page_title="영도 러너 대시보드", layout="wide")
st.markdown("## 🏃‍♂️ 영도 구청 크루 실시간 훈련 현황")

df = fetch_data()

if not df.empty:
    # 상단 하이라이트 지표
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏁 총 누적 거리", f"{df['거리(km)'].sum():.1f} km")
    c2.metric("⛰️ 최고 획득 고도", f"{df['고도(m)'].max()} m")
    c3.metric("👤 활동 러너", f"{df['러너'].nunique()} 명")
    c4.metric("📝 총 기록 수", f"{len(df)} 건")
    
    st.divider()

    # 메인 차트 및 상세 표
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("📊 최근 러닝 기록")
        st.bar_chart(df.set_index('날짜')['거리(km)'])
        
    with col_right:
        st.subheader("📅 상세 로그")
        st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("노션에서 데이터를 불러오는 중입니다...")
