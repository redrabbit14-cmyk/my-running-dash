import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
import re

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 구글 드라이브 변환 함수 (보안 링크 -> 직접 이미지 링크)
def convert_google_drive_link(url):
    if not url: return None
    if 'drive.google.com' in url:
        # 공유용 주소에서 파일 ID만 추출
        match = re.search(r'd/([^/]+)', url)
        if match:
            file_id = match.group(1)
            return f'https://drive.google.com/uc?id={file_id}'
    return url

# 노션 데이터 가져오기
@st.cache_data(ttl=600)
def get_notion_data():
    NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
    DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    res = requests.post(url, headers=headers).json()
    records = []
    
    for page in res.get("results", []):
        p = page["properties"]
        try:
            name = p.get("러너", {}).get("select", {}).get("name", "")
            # 거리/날짜/시간 로직 (기존과 동일)
            dist_prop = p.get("실제 거리", {})
            dist_val = dist_prop.get("number") if dist_prop.get("type") == "number" else dist_prop.get("formula", {}).get("number", 0)
            date_str = p.get("날짜", {}).get("date", {}).get("start", "")
            
            # --- 사진 링크 추출 로직 강화 ---
            photo_prop = p.get("사진", {})
            photo_url = None
            
            # 유형 1: 텍스트 또는 URL로 입력했을 때
            if photo_prop.get("type") == "rich_text":
                texts = photo_prop.get("rich_text", [])
                if texts: photo_url = texts[0].get("text", {}).get("content", "")
            elif photo_prop.get("type") == "url":
                photo_url = photo_prop.get("url", "")
            # 유형 2: 파일과 미디어 내 '외부 링크'로 넣었을 때
            elif photo_prop.get("type") == "files":
                files = photo_prop.get("files", [])
                if files:
                    # 구글드라이브 링크는 보통 external에 저장됨
                    photo_url = files[0].get("external", {}).get("url") or files[0].get("file", {}).get("url")

            if name and date_str:
                records.append({
                    "runner": name,
                    "date": pd.to_datetime(date_str).tz_localize(None),
                    "distance": float(dist_val or 0),
                    "photo": convert_google_drive_link(photo_url)
                })
        except: continue
    return pd.DataFrame(records)

# ... (main 함수 및 렌더링 로직은 이전과 동일)
