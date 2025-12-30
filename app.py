import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
import re

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 구글 드라이브 링크 변환 함수 (보안 링크 -> 직접 이미지 링크)
def convert_google_drive_link(url):
    if not url or not isinstance(url, str): return None
    if 'drive.google.com' in url:
        # 파일 ID 추출
        match = re.search(r'd/([^/]+)', url)
        if match:
            file_id = match.group(1)
            return f'https://drive.google.com/uc?id={file_id}'
    return url

@st.cache_data(ttl=600)
def get_notion_data():
    NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
    DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    try:
        res = requests.post(url, headers=headers).json()
        pages = res.get("results", [])
    except Exception as e:
        st.error(f"노션 연결 실패: {e}")
        return pd.DataFrame()

    records = []
    for page in pages:
        p = page["properties"]
        try:
            name = p.get("러너", {}).get("select", {}).get("name", "")
            # 거리 (수식/숫자 대응)
            dist_prop = p.get("실제 거리", {})
            dist_val = dist_prop.get("number") if dist_prop.get("type") == "number" else dist_prop.get("formula", {}).get("number", 0)
            date_str = p.get("날짜", {}).get("date", {}).get("start", "")
            
            # --- 사진 링크 추출 로직 (텍스트 유형 집중 보강) ---
            photo_url = None
            photo_prop = p.get("사진", {})
            
            # 노션이 [텍스트] 유형일 때 데이터를 가져오는 가장 확실한 방법
            if photo_prop.get("type") == "rich_text":
                texts = photo_prop.get("rich_text", [])
                if texts:
                    # plain_text와 content 두 가지 모두 시도
                    photo_url = texts[0].get("plain_text") or texts[0].get("text", {}).get("content", "")
            elif photo_prop.get("type") == "url":
                photo_url = photo_prop.get("url")

            if name and date_str:
                records.append({
                    "runner": name,
                    "date": pd.to_datetime(date_str).tz_localize(None),
                    "distance": float(dist_val or 0),
                    "photo": convert_google_drive_link(photo_url) # 여기서 구글 주소로 변환
                })
        except: continue
    
    return pd.DataFrame(records)

# ... (이하 main 함수 렌더링 로직은 기존과 동일하되, 사진 출력 부분은 st.image 사용)

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = get_notion_data()
    if df.empty: return

    # (상단 현황 섹션 생략 - 이전과 동일)

    st.header("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member]
        # 해당 러너의 기록 중 사진이 있는 가장 최근 행 찾기
        member_photo = None
        if not m_all.empty:
            valid_photos = m_all[m_all['photo'].notna() & (m_all['photo'] != "")]
            if not valid_photos.empty:
                member_photo = valid_photos.iloc[0]['photo']

        with cols[idx]:
            with st.container(border=True):
                st.subheader(member)
                if member_photo:
                    # use_container_width로 카드 크기에 맞춤
                    st.image(member_photo, use_container_width=True)
                else:
                    st.markdown("<h1 style='text-align:center;'>👤</h1>", unsafe_allow_html=True)
                
                # (페이스 및 상태 정보 출력 로직 동일)
