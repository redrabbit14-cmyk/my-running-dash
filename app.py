import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
import re

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. 스타일 설정
st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .pace-text { font-size: 1rem; color: #555; font-weight: bold; margin: 5px 0; }
    div[data-testid="column"] { padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 구글 드라이브 변환 함수
def convert_google_drive_link(url):
    if not url or not isinstance(url, str): return None
    if 'drive.google.com' in url:
        match = re.search(r'd/([^/]+)', url)
        if match:
            file_id = match.group(1)
            return f'https://drive.google.com/uc?id={file_id}'
    return url

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
    
    try:
        res = requests.post(url, headers=headers).json()
        pages = res.get("results", [])
    except Exception as e:
        st.error(f"노션 연결 오류: {e}")
        return pd.DataFrame()

    records = []
    for page in pages:
        p = page["properties"]
        try:
            name = p.get("러너", {}).get("select", {}).get("name", "")
            dist_prop = p.get("실제 거리", {})
            dist_val = dist_prop.get("number") if dist_prop.get("type") == "number" else dist_prop.get("formula", {}).get("number", 0)
            date_str = p.get("날짜", {}).get("date", {}).get("start", "")
            time_rich = p.get("시간", {}).get("rich_text", [])
            time_text = time_rich[0].get("text", {}).get("content", "0") if time_rich else "0"
            elev = p.get("고도", {}).get("number", 0) or 0
            
            # 사진 링크 추출 (모든 유형 대응)
            photo_url = None
            photo_prop = p.get("사진", {})
            p_type = photo_prop.get("type")
            
            if p_type == "rich_text":
                texts = photo_prop.get("rich_text", [])
                if texts: photo_url = texts[0].get("text", {}).get("content", "")
            elif p_type == "url":
                photo_url = photo_prop.get("url", "")
            elif p_type == "files":
                files = photo_prop.get("files", [])
                if files:
                    photo_url = files[0].get("external", {}).get("url") or files[0].get("file", {}).get("url")

            if name and date_str:
                records.append({
                    "runner": name,
                    "date": pd.to_datetime(date_str).tz_localize(None),
                    "distance": float(dist_val or 0),
                    "duration_sec": parse_time_to_seconds(time_text),
                    "elevation": elev,
                    "photo": convert_google_drive_link(photo_url)
                })
        except: continue
    
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.drop_duplicates(subset=["runner", "date", "distance"], keep="first")
    return df.sort_values("date", ascending=False)

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = get_notion_data()
    
    if df.empty:
        st.warning("데이터를 불러오는 중이거나 데이터가 비어있습니다.")
        return

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    this_week = df[df["date"] >= mon]
    last_week = df[(df["date"] >= mon - timedelta(days=7)) & (df["date"] < mon)]

    # 1. 크루 현황
    st.header("📊 크루 현황")
    tw_total, lw_total = this_week["distance"].sum(), last_week["distance"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 주 크루 총합", f"{tw_total:.1f} km")
    c2.metric("지난 주 크루 총합", f"{lw_total:.1f} km")
    c3.metric("전주 대비 증감", f"{tw_total - lw_total:+.1f} km")

    st.divider()

    # 2. 크루 컨디션 체크
    st.header("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member]
        m_this_dist = this_week[this_week["runner"] == member]["distance"].sum()
        m_last_dist = last_week[last_week["runner"] == member]["distance"].sum()
        
        m_7d = m_all[m_all["date"] >= (datetime.now() - timedelta(days=7))]
        pace_display = "0'0\""
        if not m_7d.empty and m_7d["distance"].sum() > 0:
            avg_sec = m_7d["duration_sec"].sum() / m_7d["distance"].sum()
            pace_display = f"{int(avg_sec // 60)}'{int(avg_sec % 60)}\""

        member_photo = None
        if not m_all.empty:
            photo_recs = m_all[m_all['photo'].notna() & (m_all['photo'] != "")]
            if not photo_recs.empty:
                member_photo = photo_recs.iloc[0]['photo']

        with cols[idx]:
            with st.container(border=True):
                st.subheader(member)
                if member_photo:
                    st.image(member_photo, use_container_width=True)
                else:
                    st.markdown("<h1 style='text-align:center;'>👤</h1>", unsafe_allow_html=True)
                
                st.write(f"**이번 주:** {m_this_dist:.1f} km")
                st.write(f"**지난 주:** {m_last_dist:.1f} km")
                st.markdown(f"<p class='pace-text'>7일 평균 페이스: {pace_display}</p>", unsafe_allow_html=True)
                
                if not m_all.empty:
                    rest_days = (today - m_all.iloc[0]["date"]).days
                    st.write(f"**연속 휴식:** {rest_days}일째")
                    if rest_days <= 1: st.success("상태: Good 🔥")
                    elif rest_days <= 3: st.warning("상태: 주의 ⚠️")
                    else: st.error("상태: 휴식필요 💤")

    st.divider()

    # 3. Insight & Fun
    st.header("🏆 Insight & Fun")
    if not this_week.empty:
        i1, i2, i3 = st.columns(3)
        with i1:
            best_d = this_week.loc[this_week["distance"].idxmax()]
            st.info(f"🏃 **이 주의 마라토너**\n\n**{best_d['runner']}** ({best_d['distance']:.1f}km)")
        with i2:
            best_e = this_week.loc[this_week["elevation"].idxmax()]
            st.warning(f"⛰️ **이 주의 등산가**\n\n**{best_e['runner']}** ({best_e['elevation']:.0f}m)")
        with i3:
            this_week_calc = this_week.copy()
            this_week_calc['tmp_pace'] = this_week_calc['duration_sec'] / this_week_calc['distance']
            valid_p = this_week_calc[this_week_calc['tmp_pace'] > 0]
            if not valid_p.empty:
                best_p = valid_p.loc[valid_p['tmp_pace'].idxmin()]
                st.success(f"⚡ **이 주의 폭주기관차**\n\n**{best_p['runner']}** ({int(best_p['tmp_pace']//60)}'{int(best_p['tmp_pace']%60)}\")")

    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
