import streamlit as st
from notion_client import Client
import pandas as pd
import os

# 1. 설정: 환경 변수(os.environ)에서 값을 가져옵니다.
# 나중에 GitHub Settings에서 NOTION_TOKEN과 DATABASE_ID라는 이름으로 키를 등록할 예정입니다.
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

def fetch_data():
    try:
        # 키가 설정되지 않았을 경우를 대비한 체크
        if not NOTION_TOKEN or not DATABASE_ID:
            st.error("설정 오류: API 키 또는 데이터베이스 ID가 환경 변수에 등록되지 않았습니다.")
            return pd.DataFrame()

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
            
            # 숫자 데이터(거리, 고도) 추출
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
else:
    st.info("데이터베이스에서 가져올 기록이 없거나 연결 설정을 확인 중입니다.")
