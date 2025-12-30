import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. CSS: 시안 스타일 반영 (이미지 스타일 및 카드 배치 최적화)
st.markdown("""
    <style>
    .crew-card {
        border-radius: 15px; padding: 25px 20px; text-align: center;
        background-color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        margin-bottom: 20px; border: 1px solid #eee;
        min-height: 420px; /* 카드 높이 통일 */
    }
    .status-good { border-top: 8px solid #28a745; }
    .status-warning { border-top: 8px solid #ffc107; }
    .status-danger { border-top: 8px solid #dc3545; }
    
    .profile-img { 
        border-radius: 50%; 
        object-fit: cover; 
        width: 110px; 
        height: 110px; 
        border: 3px solid #f8f9fa;
        margin-bottom: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .default-icon { font-size: 80px; margin-bottom: 15px; display: block; }
    
    .metric-label { font-size: 0.85rem; color: #888; margin-top: 12px; }
    .metric-value { font-size: 1.25rem; font-weight: bold; color: #222; margin-bottom: 5px; }
    h3 { margin-top: 10px; margin-bottom: 5px; color: #333; }
    </style>
    """, unsafe_allow_html=True)

# 데이터 변환 함수
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
    # GitHub Secrets 또는 로컬 환경변수에서 로드
    NOTION_TOKEN = st.secrets.get("NOTION_TOKEN") or os.environ.get("NOTION_TOKEN")
    DATABASE_ID = st.secrets.get("DATABASE_ID") or os.environ.get("DATABASE_ID")
    
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
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
            
            # 사진 URL 추출 (정교화)
            img_files = p.get("사진", {}).get("files", [])
            photo = None
            if img_files:
                f = img_files[0]
                photo = f.get("file", {}).get("url") or f.get("external", {}).get("url")
            
            elev = p.get("고도", {}).get("number", 0) or 0
            
            if name and date_str:
                records.append({
                    "runner": name,
                    "date": pd.to_datetime(date_str).tz_localize(None),
                    "distance": float(dist_val),
                    "duration_sec": parse_time_to_seconds(time_text),
                    "photo": photo,
                    "elevation": elev
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
        st.info("데이터를 불러오는 중입니다... 노션 설정을 확인해주세요.")
        return

    # 날짜 계산
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6, hours=23, minutes=59)
    last_mon = mon - timedelta(days=7)
    last_sun = mon - timedelta(seconds=1)

    # --- 섹션 1: 크루 현황 ---
    st.header("📊 크루 현황")
    this_week = df[(df["date"] >= mon) & (df["date"] <= sun)]
    last_week = df[(df["date"] >= last_mon) & (df["date"] <= last_sun)]
    
    tw_total = this_week["distance"].sum()
    lw_total = last_week["distance"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 주 크루 총합", f"{tw_total:.1f} km")
    c2.metric("지난 주 크루 총합", f"{lw_total:.1f} km")
    diff = tw_total - lw_total
    delta_val = f"{((diff/lw_total*100) if lw_total>0 else 0):.1f}%"
    c3.metric("전주 대비 증감", f"{diff:+.1f} km", delta=delta_val)

    st.divider()

    # --- 섹션 2: 크루 컨디션 체크 ---
    st.header("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member]
        m_this_dist = this_week[this_week["runner"] == member]["distance"].sum()
        m_last_dist = last_week[last_week["runner"] == member]["distance"].sum()
        
        # 최근 7일 페이스
        m_7d = m_all[m_all["date"] >= (datetime.now() - timedelta(days=7))]
        pace_display = "0'0\""
        if not m_7d.empty and m_7d["distance"].sum() > 0:
            avg_sec = m_7d["duration_sec"].sum() / m_7d["distance"].sum()
            pace_display = f"{int(avg_sec // 60)}'{int(avg_sec % 60)}\""

        # 휴식 상태
        rest_days = (today - m_all.iloc[0]["date"]).days if not m_all.empty else 0
        card_class = "status-good" if rest_days <= 1 else "status-warning" if rest_days <= 3 else "status-danger"
        status_text = "Good 🔥" if rest_days <= 1 else "주의 ⚠️" if rest_days <= 3 else "휴식필요 💤"

        # 사진 처리
        member_photo = None
        if not m_all.empty:
            photos_available = m_all[m_all['photo'].notna() & (m_all['photo'] != "")]
            if not photos_available.empty:
                member_photo = photos_available.iloc[0]['photo']

        img_tag = f'<img src="{member_photo}" class="profile-img">' if member_photo else '<span class="default-icon">👤</span>'

        with cols[idx]:
            # 모든 내용을 하나의 HTML div(crew-card) 안에 포함하여 레이아웃 고정
            st.markdown(f"""
                <div class="crew-card {card_class}">
                    {img_tag}
                    <h3>{member}</h3>
                    <div class="metric-label">이번 주 / 지난 주</div>
                    <div class="metric-value">{m_this_dist:.1f}km / {m_last_dist:.1f}km</div>
                    <div class="metric-label">7일 평균 페이스</div>
                    <div class="metric-value">{pace_display}</div>
                    <div class="metric-label">연속 휴식일</div>
                    <div class="metric-value">{rest_days}일째</div>
                    <div style="margin-top:15px; font-weight:bold; font-size:1.1rem;">{status_text}</div>
                </div>
            """, unsafe_allow_html=True)

    st.divider()

    # --- 섹션 3: Insight & Fun ---
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
    else:
        st.info("이번 주 활동 데이터가 수집되면 실시간 랭킹이 표시됩니다.")

    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
