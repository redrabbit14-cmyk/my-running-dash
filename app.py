import streamlit as st

st.set_page_config(page_title="테스트", layout="wide")

st.title("✅ 패키지 테스트 성공!")

st.success("Streamlit 실행됨 ✅")

try:
    from notion_client import Client
    st.success("notion-client ✅")
except:
    st.error("❌ notion-client 실패")
    
try:
    import pandas as pd
    st.success("pandas ✅")
except:
    st.error("❌ pandas 실패")
    
try:
    import plotly.express as px
    st.success("plotly ✅")
except:
    st.error("❌ plotly 실패")
