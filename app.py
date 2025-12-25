import streamlit as st
from notion_client import Client
import pandas as pd

# 1. 노션 보안 키 설정 (따옴표 필수!)
NOTION_TOKEN = "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"
DATABASE_ID = "2d18ddf6369c8077a12ad817fde87b5b"

# 2. 데이터 불러오기 함수
def fetch_data():
    notion = Client(auth=NOTION_TOKEN)
    
    # 가장 기초적이고 안전한 방식으로 데이터 요청
    try:
        response = notion.databases.query(**{"database_id": DATABASE_ID})
        results = response.get("results", [])
    except Exception as e:
        st.error(f"노션 API 연결 실패: {e}")
        return pd.DataFrame()

    data = []
    for row in results:
        props = row.get("properties", {})
        try:
            # 안전하게 데이터를 하나씩 추출
            data.append({
                "이름": props.get("이름", {}).get("title", [{}])[0].get("plain_text", "제목없음"),
                "날짜": props.get("날짜", {}).get("date", {}).get("start", "") if props.get("날짜", {}).get("date") else "",
                "러너": props.get("러너", {}).get("select", {}).get("name", "미정") if props.get("러너", {}).get("select") else "미정",
                "거리": props.get("실제 거리", {}).get("number", 0) if props.get("실제 거리", {}).get("number") else 0,
                "고도": props.get("고도", {}).get("number", 0) if props.get("고도", {}).get("number") else 0
            })
        except:
            continue
            
    return pd.DataFrame(data)

# 3. 화면 구성
st.set_page_config(page_title="영도 러너 대시보드", layout="wide")
st.title("🏃‍♂️ 우리 크루 훈련 실시간 현황")

try:
    df = fetch_data()
    
    if not df.empty:
        # 상단 대시보드 요약
        c1, c2, c3 = st.columns(3)
        c1.metric("총 거리", f"{df['거리'].sum():.1f} km")
        c2.metric("최대 고도", f"{df['고도'].max()} m")
        c3.metric("총 기록 수", f"{len(df)} 건")

        st.divider()
        st.subheader("📊 훈련 상세 데이터")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("데이터를 가져왔으나 표시할 내용이 없습니다. 노션 표에 행이 추가되어 있는지 확인해 주세요.")

except Exception as e:
    st.error(f"화면 구성 중 오류 발생: {e}")
