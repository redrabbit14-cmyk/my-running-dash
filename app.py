import streamlit as st
from notion_client import Client
import pandas as pd

# 1. 설정 (지금 복사한 최신 ntn_ 키를 정확히 넣어주세요)
NOTION_TOKEN = "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"
DATABASE_ID = "2d18ddf6369c8077a12ad817fde87b5b"

def fetch_data():
    try:
        notion = Client(auth=NOTION_TOKEN)
        response = notion.databases.query(database_id=DATABASE_ID)
        results = response.get("results", [])
        data = []
        
        for row in results:
            props = row.get("properties", {})
            # 이름/날짜/러너 추출
            name = props.get("이름", {}).get("title", [{}])[0].get("plain_text", "기록")
            date = props.get("날짜", {}).get("date", {}).get("start", "")[:10] if props.get("날짜", {}).get("date") else ""
            runner = props.get("러너", {}).get("select", {}).get("name", "미정")
            
            # 숫자 데이터(거리, 고도) 추출 - 컬럼명을 유연하게 체크
            dist = 0
            for k, v in props.items():
                if "거리" in k and v.get("number") is not None:
                    dist = v["number"]
            
            elev = 0
            for k, v in props.items():
                if "고도" in k and v.get("number") is not None:
                    elev = v["number"]
            
            data.append({"날짜": date, "러너": runner, "거리": dist, "고도": elev})
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"연결 실패: {e}")
        return pd.DataFrame()

# 화면 출력
st.set_page_config(page_title="러닝 대시보드", layout="wide")
st.title("🏃‍♂️ 우리 크루 실시간 훈련 현황")

df = fetch_data()
if not df.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("🏁 총 거리", f"{df['거리'].sum():.1f} km")
    c2.metric("⛰️ 최고 고도", f"{df['고도'].max()} m")
    c3.metric("📝 기록 수", f"{len(df)} 건")
    
    st.divider()
    st.bar_chart(df.groupby("날짜")["거리"].sum())
    st.dataframe(df, use_container_width=True)
