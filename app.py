import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
import re

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. 구글 드라이브 링크 직접 이미지 주소로 변환
def convert_google_drive_link(url):
    try:
        if not url or not isinstance(url, str): return None
        url = url.strip()
        if 'drive.google.com' in url:
            # 주소에서 파일 ID만 추출 (다양한 링크 형식 대응)
            file_id = None
            if 'file/d/' in url:
                file_id = url.split('file/d/')[1].split('/')[0]
            elif 'id=' in url:
                file_id = url.split('id=')[1].split('&')[0]
            
            if file_id:
                return f'https://drive.google.com/uc?id={file_id}'
        return url
    except:
        return None

# 3. 노션 데이터 수집 함수
@st.cache_data(ttl=300)
def get_notion_data():
    NOTION_TOKEN = st.secrets.get("NOTION_TOKEN")
    DATABASE_ID = st.secrets.get("DATABASE_ID")
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    try:
        res = requests.post(url, headers=headers).json()
        pages = res.get("results", [])
    except:
        return pd.DataFrame()

    records = []
    for page in pages:
        p = page["properties"]
        try:
            # 기본 데이터 추출
            name = p.get("러너", {}).get("select", {}).get("name", "")
            date_str = p.get("날짜", {}).get("date", {}).get("start", "")
            
            dist_prop = p.get("실제 거리", {})
            dist_val = dist_prop.get("number") if dist_prop.get("type") == "number" else dist_prop.get("formula", {}).get("number", 0)
            
            # --- 사진 링크 추출 (이 부분을 대폭 강화했습니다) ---
            photo_url = ""
            photo_prop = p.get("사진", {})
            
            # 텍스트(rich_text) 유형일 때
            if photo_prop.get("type") == "rich_text":
                text_list = photo_prop.get("rich_text", [])
                if text_list:
                    # plain_text 속성을 우선적으로 가져옴
                    photo_url = text_list[0].get("plain_text", "").strip()
            # 혹시 URL 유형으로 되어 있을 때
            elif photo_prop.get("type") == "url":
                photo_url = photo_prop.get("url", "").strip()

            if name and date_str:
                records.append({
                    "runner": name,
                    "date": pd.to_datetime(date_str).tz_localize(None),
                    "distance": float(dist_val or 0),
                    "photo_link": convert_google_drive_link(photo_url)
                })
        except:
            continue
    
    return pd.DataFrame(records)

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = get_notion_data()
    
    if df.empty:
        st.warning("데이터를 불러오지 못했습니다. 노션의 컬럼 구성을 다시 확인해주세요.")
        return

    # 주간 데이터 계산 (이번 주/지난 주 비교)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    this_week = df[df["date"] >= mon]
    last_week = df[(df["date"] >= mon - timedelta(days=7)) & (df["date"] < mon)]

    # 1. 크루 현황
    st.header("📊 크루 현황")
    c1, c2, c3 = st.columns(3)
    tw_total = this_week["distance"].sum()
    lw_total = last_week["distance"].sum()
    c1.metric("이번 주 합계", f"{tw_total:.1f} km")
    c2.metric("지난 주 합계", f"{lw_total:.1f} km")
    c3.metric("전주 대비", f"{tw_total - lw_total:+.1f} km")

    st.divider()

    # 2. 크루 컨디션 (사진 포함)
    st.header("💪 크루 컨디션 체크")
    crew = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew))

    for idx, member in enumerate(crew):
        m_data = df[df["runner"] == member]
        m_this = this_week[this_week["runner"] == member]["distance"].sum()
        
        # 가장 최근 사진 주소 가져오기
        member_photo = None
        if not m_data.empty:
            # 사진 링크가 있는 행 중 가장 최근 것
            photo_rows = m_data[m_data["photo_link"].notna() & (m_data["photo_link"] != "")]
            if not photo_rows.empty:
                member_photo = photo_rows.iloc[0]["photo_link"]

        with cols[idx]:
            with st.container(border=True):
                st.subheader(member)
                if member_photo:
                    st.image(member_photo, use_container_width=True)
                else:
                    st.markdown("<h1 style='text-align:center;'>👤</h1>", unsafe_allow_html=True)
                
                st.write(f"**이번 주 기록:** {m_this:.1f} km")
                
                if not m_data.empty:
                    rest = (today - m_data.iloc[0]["date"]).days
                    if rest <= 1: st.success("상태: Good 🔥")
                    elif rest <= 3: st.warning("상태: 주의 ⚠️")
                    else: st.error("상태: 휴식필요 💤")

    st.button("🔄 데이터 새로고침", on_click=st.cache_data.clear)

if __name__ == "__main__":
    main()
