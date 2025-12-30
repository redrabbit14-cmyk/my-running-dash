import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. CSS 수정: 카드와 텍스트 정렬 최적화
st.markdown("""
    <style>
    .crew-card {
        border-radius: 15px; padding: 20px; text-align: center;
        background-color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        margin-bottom: 20px; border: 1px solid #eee;
    }
    .status-good { border-top: 8px solid #28a745; }
    .status-warning { border-top: 8px solid #ffc107; }
    .status-danger { border-top: 8px solid #dc3545; }
    
    .metric-label { font-size: 0.85rem; color: #888; margin-top: 10px; }
    .metric-value { font-size: 1.15rem; font-weight: bold; color: #222; margin-bottom: 3px; }
    h3 { margin: 10px 0; color: #333; }
    
    /* Streamlit 이미지 센터 정렬용 */
    [data-testid="stHorizontalBlock"] > div {
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    </style>
    """, unsafe_allow_html=True)

# 데이터 변환 및 노션 API 호출 (기존 로직 동일 유지)
def parse_time_to_seconds(time_str):
    if not time_str or time_str == "0": return 0
    try:
        parts = str(time_str).strip().split(':')
        if len(parts) == 3: return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        elif len(parts) == 2: return int(parts[0])*60 + int(parts[1])
        else: return int(parts[0]) if parts[0].isdigit() else 0
    except: return 0

@st.cache_data(ttl=600)
def get_notion_data():
    NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
    DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    all_pages = []
    has_more, next_cursor = True, None
    while has_more:
        payload = {"start_cursor": next_cursor} if next_cursor else {}
        res = requests.post(url, headers=headers, json=payload).json()
        all_pages.extend(res.get("results", []))
        has_more = res.get("has_more", False)
        next_cursor = res.get("next_cursor")

    records = []
    for page in all_pages:
        p = page["properties"]
        try:
            name = p.get("러너", {}).get("select", {}).get("name", "")
            dist_val = p.get("실제 거리", {}).get("number") or p.get("실제 거리", {}).get("formula", {}).get("number", 0)
            date_str = p.get("날짜", {}).get("date", {}).get("start", "")
            time_rich = p.get("시간", {}).get("rich_text", [])
            time_text = time_rich[0].get("text", {}).get("content", "0") if time_rich else "0"
            
            # 사진 URL 추출
            img_files = p.get("사진", {}).get("files", [])
            photo = None
            if img_files:
                f = img_files[0]
                # Notion 업로드 파일인 경우 'file' 키 안에 url이 있음
                photo = f.get("file", {}).get("url") or f.get("external", {}).get("url")
            
            if name and date_str:
                records.append({
                    "runner": name, "date": pd.to_datetime(date_str).tz_localize(None),
                    "distance": float(dist_val), "duration_sec": parse_time_to_seconds(time_text),
                    "photo": photo, "elevation": p.get("고도", {}).get("number", 0) or 0
                })
        except: continue
    df = pd.DataFrame(records)
    if not df.empty: df = df.drop_duplicates(subset=["runner", "date", "distance"], keep="first")
    return df.sort_values("date", ascending=False)

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = get_notion_data()
    if df.empty: return

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    this_week = df[(df["date"] >= mon)]
    last_week = df[(df["date"] >= mon - timedelta(days=7)) & (df["date"] < mon)]

    # 섹션 1: 현황 생략 (기존 코드와 동일)

    st.header("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member]
        m_this_dist = this_week[this_week["runner"] == member]["distance"].sum()
        m_last_dist = last_week[last_week["runner"] == member]["distance"].sum()
        
        # 최근 기록에서 사진 찾기
        member_photo = None
        if not m_all.empty:
            photos = m_all[m_all['photo'].notna() & (m_all['photo'] != "")]
            if not photos.empty:
                member_photo = photos.iloc[0]['photo']

        # 휴식일 및 상태 계산
        rest_days = (today - m_all.iloc[0]["date"]).days if not m_all.empty else 0
        card_class = "status-good" if rest_days <= 1 else "status-warning" if rest_days <= 3 else "status-danger"
        status_text = "Good 🔥" if rest_days <= 1 else "주의 ⚠️" if rest_days <= 3 else "휴식필요 💤"

        with cols[idx]:
            # 카드 박스 시작 (HTML)
            st.markdown(f'<div class="crew-card {card_class}">', unsafe_allow_html=True)
            
            # --- 사진 표시: st.image 사용 (보안 URL 처리 최적화) ---
            if member_photo:
                try:
                    # 사진을 원형으로 보여주기 위해 스타일을 입힌 컨테이너 안에서 st.image 호출
                    st.image(member_photo, width=110)
                except:
                    st.markdown("<h1 style='font-size:80px; margin:0;'>👤</h1>", unsafe_allow_html=True)
            else:
                st.markdown("<h1 style='font-size:80px; margin:0;'>👤</h1>", unsafe_allow_html=True)
            
            # 정보 표시 (HTML)
            st.markdown(f"""
                    <h3>{member}</h3>
                    <div class="metric-label">이번 주 / 지난 주</div>
                    <div class="metric-value">{m_this_dist:.1f}km / {m_last_dist:.1f}km</div>
                    <div class="metric-label">연속 휴식일</div>
                    <div class="metric-value">{rest_days}일째</div>
                    <div style="margin-top:15px; font-weight:bold; color: {'#28a745' if rest_days <=1 else '#ffc107' if rest_days <=3 else '#dc3545'}">{status_text}</div>
                </div>
            """, unsafe_allow_html=True)

    # ... 이하 하단부(Insight & Fun) 동일
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
