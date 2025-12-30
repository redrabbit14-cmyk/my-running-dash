import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. CSS: 카드 스타일 및 메트릭 가독성 향상
st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .status-box { padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; margin-top: 10px; }
    .pace-text { font-size: 1.1rem; color: #444; font-weight: bold; margin: 5px 0; }
    </style>
    """, unsafe_allow_html=True)

# 시간 변환 함수
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
            # 실제 거리 (수식 또는 숫자)
            dist_prop = p.get("실제 거리", {})
            dist_val = dist_prop.get("number") if dist_prop.get("type") == "number" else dist_prop.get("formula", {}).get("number", 0)
            
            date_str = p.get("날짜", {}).get("date", {}).get("start", "")
            time_rich = p.get("시간", {}).get("rich_text", [])
            time_text = time_rich[0].get("text", {}).get("content", "0") if time_rich else "0"
            
            # 사진
            photo = None
            img_files = p.get("사진", {}).get("files", [])
            if img_files:
                f = img_files[0]
                photo = f.get("file", {}).get("url") or f.get("external", {}).get("url")
            
            if name and date_str:
                records.append({
                    "runner": name,
                    "date": pd.to_datetime(date_str).tz_localize(None),
                    "distance": float(dist_val or 0),
                    "duration_sec": parse_time_to_seconds(time_text),
                    "photo": photo
                })
        except: continue
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.drop_duplicates(subset=["runner", "date", "distance"], keep="first")
    return df.sort_values("date", ascending=False)

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = get_notion_data()
    if df.empty: return

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    
    # 상단 현황
    st.header("📊 크루 현황")
    this_week = df[df["date"] >= mon]
    last_week = df[(df["date"] >= mon - timedelta(days=7)) & (df["date"] < mon)]
    
    tw_total, lw_total = this_week["distance"].sum(), last_week["distance"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 주 크루 총합", f"{tw_total:.1f} km")
    c2.metric("지난 주 크루 총합", f"{lw_total:.1f} km")
    c3.metric("전주 대비 증감", f"{tw_total - lw_total:+.1f} km")

    st.divider()

    # 크루 컨디션 체크 (페이스 포함)
    st.header("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member]
        m_this_dist = this_week[this_week["runner"] == member]["distance"].sum()
        m_last_dist = last_week[last_week["runner"] == member]["distance"].sum()
        
        # --- 7일 평균 페이스 계산 ---
        m_7d = m_all[m_all["date"] >= (datetime.now() - timedelta(days=7))]
        pace_display = "0'0\""
        if not m_7d.empty and m_7d["distance"].sum() > 0:
            avg_sec = m_7d["duration_sec"].sum() / m_7d["distance"].sum()
            pace_display = f"{int(avg_sec // 60)}'{int(avg_sec % 60)}\""
        # ---------------------------

        with cols[idx]:
            with st.container(border=True):
                st.subheader(member)
                
                # 사진 (공간 확보)
                st.markdown("<h1 style='text-align:center; margin:0;'>👤</h1>", unsafe_allow_html=True)
                
                # 데이터 표시
                st.write(f"**이번 주:** {m_this_dist:.1f} km")
                st.write(f"**지난 주:** {m_last_dist:.1f} km")
                
                # 페이스 및 휴식 정보
                st.markdown(f"<p class='pace-text'>7일 평균 페이스: {pace_display}</p>", unsafe_allow_html=True)
                
                if not m_all.empty:
                    rest_days = (today - m_all.iloc[0]["date"]).days
                    st.write(f"**연속 휴식:** {rest_days}일째")
                    
                    if rest_days <= 1: st.success("상태: Good 🔥")
                    elif rest_days <= 3: st.warning("상태: 주의 ⚠️")
                    else: st.error("상태: 휴식필요 💤")
                else:
                    st.info("기록 없음")

    st.divider()
    # 하단 Insight & Fun (기존 로직)
    # ... (생략 가능하나 필요시 추가)

if __name__ == "__main__":
    main()
