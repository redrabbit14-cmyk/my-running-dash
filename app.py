import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. CSS: 깔끔한 대시보드 스타일
st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .pace-text { font-size: 1rem; color: #555; font-weight: bold; margin: 5px 0; }
    div[data-testid="stExpander"] { border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
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
            # 실제 거리 (수식 결과 처리)
            dist_prop = p.get("실제 거리", {})
            dist_val = dist_prop.get("number") if dist_prop.get("type") == "number" else dist_prop.get("formula", {}).get("number", 0)
            
            date_str = p.get("날짜", {}).get("date", {}).get("start", "")
            time_rich = p.get("시간", {}).get("rich_text", [])
            time_text = time_rich[0].get("text", {}).get("content", "0") if time_rich else "0"
            
            # 고도 (8열)
            elev = p.get("고도", {}).get("number", 0) or 0
            
            # 사진 (10열)
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
                    "elevation": elev,
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
    if df.empty:
        st.warning("데이터가 없습니다.")
        return

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    this_week = df[df["date"] >= mon]
    last_week = df[(df["date"] >= mon - timedelta(days=7)) & (df["date"] < mon)]

    # --- 섹션 1: 크루 현황 ---
    st.header("📊 크루 현황")
    tw_total, lw_total = this_week["distance"].sum(), last_week["distance"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 주 크루 총합", f"{tw_total:.1f} km")
    c2.metric("지난 주 크루 총합", f"{lw_total:.1f} km")
    c3.metric("전주 대비 증감", f"{tw_total - lw_total:+.1f} km", delta=f"{((tw_total-lw_total)/lw_total*100 if lw_total>0 else 0):.1f}%")

    st.divider()

    # --- 섹션 2: 크루 컨디션 체크 (페이스 포함) ---
    st.header("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member]
        m_this_dist = this_week[this_week["runner"] == member]["distance"].sum()
        m_last_dist = last_week[last_week["runner"] == member]["distance"].sum()
        
        # 7일 평균 페이스 계산
        m_7d = m_all[m_all["date"] >= (datetime.now() - timedelta(days=7))]
        pace_display = "0'0\""
        if not m_7d.empty and m_7d["distance"].sum() > 0:
            avg_sec = m_7d["duration_sec"].sum() / m_7d["distance"].sum()
            pace_display = f"{int(avg_sec // 60)}'{int(avg_sec % 60)}\""

        with cols[idx]:
            with st.container(border=True):
                st.subheader(member)
                st.markdown("<h1 style='text-align:center; margin:0;'>👤</h1>", unsafe_allow_html=True)
                st.write(f"**이번 주 / 지난 주**")
                st.write(f"{m_this_dist:.1f}km / {m_last_dist:.1f}km")
                st.markdown(f"<p class='pace-text'>7일 평균 페이스: {pace_display}</p>", unsafe_allow_html=True)
                
                if not m_all.empty:
                    rest_days = (today - m_all.iloc[0]["date"]).days
                    st.write(f"**연속 휴식:** {rest_days}일째")
                    if rest_days <= 1: st.success("상태: Good 🔥")
                    elif rest_days <= 3: st.warning("상태: 주의 ⚠️")
                    else: st.error("상태: 휴식필요 💤")

    st.divider()

    # --- 섹션 3: Insight & Fun (랭킹 섹션 복구) ---
    st.header("🏆 Insight & Fun")
    if not this_week.empty:
        i1, i2, i3 = st.columns(3)
        with i1:
            best_d = this_week.loc[this_week["distance"].idxmax()]
            st.info(f"🏃 **이 주의 마라토너**\n\n**{best_d['runner']}** ({best_d['distance']:.1f}km)")
        with i2:
            # 고도 데이터 기준
            best_e = this_week.loc[this_week["elevation"].idxmax()]
            st.warning(f"⛰️ **이 주의 등산가**\n\n**{best_e['runner']}** ({best_e['elevation']:.0f}m)")
        with i3:
            # 페이스 기준 (가장 빠른 사람)
            this_week_calc = this_week.copy()
            this_week_calc['tmp_pace'] = this_week_calc['duration_sec'] / this_week_calc['distance']
            valid_p = this_week_calc[this_week_calc['tmp_pace'] > 0]
            if not valid_p.empty:
                best_p = valid_p.loc[valid_p['tmp_pace'].idxmin()]
                p_min, p_sec = int(best_p['tmp_pace']//60), int(best_p['tmp_pace']%60)
                st.success(f"⚡ **이 주의 폭주기관차**\n\n**{best_p['runner']}** ({p_min}'{p_sec}\")")
    else:
        st.info("이번 주 활동 데이터가 수집되면 랭킹이 표시됩니다.")

    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
