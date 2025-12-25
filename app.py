import streamlit as st
from notion_client import Client
import pandas as pd

# 1. 노션 보안 키 설정
NOTION_TOKEN = "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"
DATABASE_ID = "2d18ddf6369c8077a12ad817fde87b5b"

notion = Client(auth=NOTION_TOKEN)

# 2. 데이터 불러오기 함수
def fetch_data():
    results = notion.databases.query(database_id=DATABASE_ID).get("results")
    data = []
    for row in results:
        props = row["properties"]
        # 각 필드명은 노션 표의 제목과 일치해야 합니다
        data.append({
            "이름": props["이름"]["title"][0]["text"]["content"] if props["이름"]["title"] else "제목없음",
            "날짜": props["날짜"]["date"]["start"] if props["날짜"]["date"] else "",
            "러너": props["러너"]["select"]["name"] if props["러너"]["select"] else "미정",
            "거리": props["실제 거리"]["number"] if props["실제 거리"]["number"] else 0,
            "고도": props["고도"]["number"] if props["고도"]["number"] else 0
        })
    return pd.DataFrame(data)

# 3. 대시보드 화면 구성
st.set_page_config(page_title="영도 러너 대시보드", layout="wide")
st.title("🏃‍♂️ 우리 크루 훈련 실시간 현황")

try:
    df = fetch_data()
    
    # 상단 요약 수치 (Metric)
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 주 총 거리", f"{df['거리'].sum():.1f} km")
    c2.metric("최고 고도", f"{df['고도'].max()} m")
    c3.metric("참여 러너 수", f"{df['러너'].nunique()} 명")

    # 데이터 표
    st.subheader("📊 상세 기록")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"연결 오류 발생: {e}")
