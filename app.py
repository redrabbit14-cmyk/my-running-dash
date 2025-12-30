import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
import re

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. 구글 드라이브 링크 변환 함수 (직접 다운로드 주소로 강제 변환)
def convert_google_drive_link(url):
    try:
        if not url or not isinstance(url, str): return None
        if 'drive.google.com' in url:
            # 주소에서 파일 ID만 추출
            match = re.search(r'd/([^/]+)', url)
            if match:
                file_id = match.group(1)
                return f'https://drive.google.com/uc?id={file_id}'
        return url
    except:
        return None

# 3. 시간 문자열 변환 함수
def parse_time_to_seconds(time_str):
    if not time_str or time_str == "0": return 0
    try:
        parts = str(time_str).strip().split(':')
        if len(parts) == 3: return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        elif len(parts) == 2: return int(parts[0])*60 + int(parts[1])
        else: return int(parts[0]) if parts[0].isdigit() else 0
    except:
        return 0

# 4. 노션 데이터 가져오기
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
            # 1. 러너 이름
            name = p.get("러너", {}).get("select", {}).get("name", "")
            
            # 2. 날짜
            date_str = p.get("날짜", {}).get("date", {}).get("start", "")
            
            # 3. 실제 거리 (숫자 또는 수식)
            dist_prop = p.get("실제 거리", {})
            dist_val = dist_prop.get("number") if dist_prop.get("type") == "number" else dist_prop.get("formula", {}).get("number", 0)
            
            # 4. 시간 (텍스트)
            time_rich = p.get("시간", {}).get("rich_text", [])
            time_text = time_rich[0].get("plain_text", "0") if time_rich else "0"
            
            # 5. 사진 (텍스트 또는 URL 컬럼 대응)
            photo_url = None
            photo_prop = p.get("사진", {})
            p_type = photo_prop.get("type")
            if p_type == "rich_text":
                texts = photo_prop.get("rich_text", [])
                if texts: photo_url = texts[0].get("plain_text", "")
            elif p_type == "url":
                photo_url = photo_prop.get("url", "")
            
            # 6. 고도
            elev = p.get("고도", {}).get("number", 0) or 0

            if name and date_str:
                records.append({
                    "runner": name,
                    "date": pd.to_datetime(date_str).tz_localize(None),
                    "distance": float(dist_val or 0),
                    "duration_sec": parse_time_to_seconds(time_text),
                    "elevation": elev,
                    "photo": convert_google_drive_link(photo_url)
                })
        except:
            continue
    
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("date", ascending=False)
    return df

# 5. 메인 대시보드 실행
def main():
    st.title("🏃 러닝 크루 대시보드")
    df = get_notion_data()
    
    if df.empty:
        st.error("데이터를 불러오지 못했습니다. 노션의 컬럼명과 Secrets 설정을 확인해주세요.")
        return

    # 주간 데이터 필터링
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    this_week = df[df["date"] >= mon]
    last_week = df[(df["date"] >= mon - timedelta(days=7)) & (df["date"] < mon)]

    # --- 1. 크루 현황 섹션 ---
    st.header("📊 크루 현황")
    tw_total = this_week["distance"].sum()
    lw_total = last_week["distance"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 주 크루 총합", f"{tw_total:.1f} km")
    c2.metric("지난 주 크루 총합", f"{lw_total:.1f} km")
    c3.metric("전주 대비 증감", f"{tw_total - lw_total:+.1f} km")

    st.divider()

    # --- 2. 크루 컨디션 체크 섹션 ---
    st.header("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member]
        m_this_dist = this_week[this_week["runner"] == member]["distance"].sum()
        m_last_dist = last_week[last_week["runner"] == member]["distance"].sum()
        
        # 7일 평균 페이스
        m_7d = m_all[m_all["date"] >= (datetime.now() - timedelta(days=7))]
        pace_display = "0'0\""
        if not m_7d.empty and m_7d["distance"].sum() > 0:
            avg_sec = m_7d["duration_sec"].sum() / m_7d["distance"].sum()
            pace_display = f"{int(avg_sec // 60)}'{int(avg_sec % 60)}\""

        # 사진 데이터 찾기 (해당 멤버의 가장 최근 사진)
        member_photo = None
        if not m_all.empty:
            valid_photos = m_all[m_all['photo'].notna() & (m_all['photo'] != "")]
            if not valid_photos.empty:
                member_photo = valid_photos.iloc[0]['photo']

        with cols[idx]:
            with st.container(border=True):
                st.subheader(member)
                if member_photo:
                    st.image(member_photo, use_container_width=True)
                else:
                    st.markdown("<h2 style='text-align:center;'>👤</h2>", unsafe_allow_html=True)
                
                st.write(f"**이번 주:** {m_this_dist:.1f} km")
                st.write(f"**지난 주:** {m_last_dist:.1f} km")
                st.write(f"**평균 페이스:** {pace_display}")
                
                if not m_all.empty:
                    rest_days = (today - m_all.iloc[0]["date"]).days
                    if rest_days <= 1: st.success("상태: Good 🔥")
                    elif rest_days <= 3: st.warning("상태: 주의 ⚠️")
                    else: st.error("상태: 휴식필요 💤")

    st.divider()
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
