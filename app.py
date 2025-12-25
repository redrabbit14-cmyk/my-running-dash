import streamlit as st
from notion_client import Client
import pandas as pd

# 1. 노션 보안 키 및 DB 설정 (따옴표 확인 필수!)
NOTION_TOKEN = "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"
DATABASE_ID = "2d18ddf6369c8077a12ad817fde87b5b"

# 2. 데이터 불러오기 함수
def fetch_data():
    # 클라이언트를 함수 안에서 생성하여 연결 안정성 확보
    client = Client(auth=NOTION_TOKEN)
    
    # query 명령어 대신 가장 기초적인 방식으로 데이터 요청
    try:
        response = client.databases.query(database_id=DATABASE_ID)
        results = response.get("results", [])
    except Exception as e:
        st.error(f"노션 API 연결 자체에 실패했습니다: {e}")
        return pd.DataFrame()

    data = []
    for row in results:
        props = row["properties"]
        try:
            # 각 데이터 추출 (컬럼명이 노션과 다를 경우 대비하여 안전하게 처리)
            item = {
                "이름": props.get("이름", {}).get("title", [{}])[0].get("text", {}).get("content", "제목없음"),
                "날짜": props.get("날짜", {}).get("date", {}).get("start", "") if props.get("날짜", {}).get("date") else "",
                "러너": props.get("러너", {}).get("select", {}).get("name", "미정") if props.get("러너", {}).get("select") else "미정",
                "거리": props.get("실제 거리", {}).get("number", 0) if props.get("실제 거리", {}).get("number") else 0,
                "고도": props.get("고도", {}).get("number", 0) if props.get("고도", {}).get("number") else 0
            }
            data.append(item)
        except Exception:
            continue
            
    return pd.DataFrame(data)

# 3. 대시보드 화면 구성
st.set_page_config(page_title="영도 러너 대시보드", layout="wide")
st.title("🏃‍♂️ 우리 크루 훈련 실시간 현황")

try:
    df = fetch_data()
    
    if not df.empty:
        # 상단 요약 수치
        col1, col2, col3 = st.columns(3)
        col1.metric("이번 주 총 거리", f"{df['거리'].sum():.1f} km")
        col2.metric("최고 고도", f"{df['고도'].max()} m")
        col3.metric("참여 러너 수", f"{df['러너'].nunique()} 명")

        # 상세 데이터 표
        st.subheader("📊 상세 기록 현황")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("노션에서 데이터를 가져왔으나 내용이 비어있습니다. 노션 페이지에 기록이 있는지 확인해 주세요.")
        
except Exception as e:
    st.error(f"대시보드 구성 중 오류 발생: {e}")
