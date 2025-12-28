import streamlit as st
import os

st.set_page_config(page_title="런닝 대시보드", layout="wide")

# 테스트용 - secrets 확인
st.title("🏃‍♂️ 런닝 대시보드 테스트")

# Secrets 상태 확인
notion_token = st.secrets.get("NOTION_TOKEN", "설정안됨")
db_id = st.secrets.get("DATABASE_ID", "설정안됨") 
weather_key = st.secrets.get("OPENWEATHER_API_KEY", "설정안됨")

st.subheader("🔑 Secrets 상태")
col1, col2, col3 = st.columns(3)
col1.metric("Notion Token", notion_token[:10] + "..." if notion_token != "설정안됨" else "❌")
col2.metric("Database ID", db_id[:10] + "..." if db_id != "설정안됨" else "❌")
col3.metric("Weather Key", weather_key[:10] + "..." if weather_key != "설정안됨" else "❌")

if notion_token == "설정안됨" or db_id == "설정안됨":
    st.error("❌ Streamlit Cloud의 Settings > Secrets 탭에서 3개 키 입력 필요!")
    st.stop()
else:
    st.success("✅ 모든 Secrets 정상!")
    st.info("이제 원본 app.py로 되돌리세요.")
