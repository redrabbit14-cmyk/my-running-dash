import streamlit as st
from notion_client import Client

st.set_page_config(layout="wide")
st.title("🔍 노션 데이터 상세 진단")

NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
DATABASE_ID = st.secrets["DATABASE_ID"]

notion = Client(auth=NOTION_TOKEN)
results = notion.databases.query(database_id=DATABASE_ID)

st.success(f"✅ {len(results['results'])}개 데이터 로드됨!")

if results['results']:
    # 첫 번째 행 전체 속성
    first_row = results['results'][0]['properties']
    st.subheader("📋 첫 번째 행 속성 목록")
    
    for prop_name, prop_data in first_row.items():
        st.write(f"**{prop_name}**")
        st.json(prop_data, expanded=False)
        st.markdown("---")
    
    # 첫 3행 데이터 미리보기
    st.subheader("📊 첫 3행 데이터")
    for i, page in enumerate(results['results'][:3]):
        st.write(f"**행 {i+1}: {page['properties'].get('날짜', {}).get('date', {}).get('start', '날짜없음')}**")
        st.json({k: v for k, v in page['properties'].items() 
                if k in ['날짜', '거리', '시간', '평균페이스', '심박수', '상태', '날씨']}, expanded=True)
else:
    st.warning("데이터 없음")
