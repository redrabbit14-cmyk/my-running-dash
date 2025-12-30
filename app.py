import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. CSS: 시안 스타일 및 카드 디자인
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
    .metric-label { font-size: 0.85rem; color: #888; margin-top: 12px; }
    .metric-value { font-size: 1.25rem; font-weight: bold; color: #222; margin-bottom: 5px; }
    .rest-badge { font-size: 0.9rem; font-weight: bold; padding: 6px; border-radius: 8px; margin-top: 10px; }
    .profile-img { border-radius: 50%; object-fit: cover; width: 100px; height: 100px; border: 3px solid #f0f0f0; }
    </style>
    """, unsafe_allow_html=True)

# 환경 설정 및 데이터 로드
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}

def time_to_seconds(time_str):
    try:
        parts = list(map(int, str(time_str).split(':')))
        if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2: return parts[0]*60 + parts[1]
        return 0
    except: return 0

@st.cache_data(ttl=600)
def get_clean_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    res = requests.post(url, headers=headers).json()
    records = []
    for page in res.get("results", []):
        p = page["properties"]
        try:
            name = p.get("러너", {}).get("select", {}).get("name", "")
            dist = p.get("실제 거리", {}).get("number") or p.get("실제 거리", {}).get("formula", {}).get("number", 0)
            date = p.get("날짜", {}).get("date", {}).get("start", "")
            time_txt = p.get("시간", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "0")
            img = p.get("사진", {}).get("files", [{}])[0].get("file", {}).get("url", "") or p.get("사진", {}).get("files", [{}])[0].get("external", {}).get("url", "")
            elev = p.get("고도", {}).get("number", 0) or 0
            if name and date:
                records.append({"runner": name, "date": date, "distance": float(dist), "duration_sec": time_to_seconds(time_txt), "photo": img, "elevation": elev})
        except: continue
    df = pd.DataFrame(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        # 중복 제거: 이름, 날짜, 거리가 같으면 중복으로 판단
        df = df.drop_duplicates(subset=["runner", "date", "distance"], keep="first")
    return df.sort_values("date", ascending=False)

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = get_clean_data()
    if df.empty: return

    # 날짜 필터 설정
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
    c3.metric("전주 대비 증감", f"{diff:+.1f} km", delta=f"{((diff/lw_total*100) if lw_total>0 else 0):.1f}%")

    st.divider()

    # --- 섹션 2: 크루 컨디션 체크 (카드형) ---
    st.header("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member]
        m_this_dist = this_week[this_week["runner"] == member]["distance"].sum()
        m_last_dist = last_week[last_week["runner"] == member]["distance"].sum()
        
        # 최근 7일 페이스 재계산
        m_7d = m_all[m_all["date"] >= (datetime.now() - timedelta(days=7))]
        pace_str = "0'0\""
        if not m_7d.empty and m_7d["distance"].sum() > 0:
            avg_sec = m_7d["duration_sec"].sum() / m_7d["distance"].sum()
            pace_str = f"{int(avg_sec//60)}'{int(avg_sec%60)}\""

        # 휴식일 계산
        rest_days = (today - m_all.iloc[0]["date"]).days if not m_all.empty else 0
        status_color = "#d4edda" if rest_days <= 1 else "#fff3cd" if rest_days <= 3 else "#f8d7da"
        status_text = "Good 🔥" if rest_days <= 1 else "주의 ⚠️" if rest_days <= 3 else "휴식필요 💤"
        card_class = "status-good" if rest_days <= 1 else "status-warning" if rest_days <= 3 else "status-danger"

        with cols[idx]:
            photo = m_all.iloc[0]["photo"] if not m_all.empty and m_all.iloc[0]["photo"] else ""
            img_tag = f'<img src="{photo}" class="profile-img">' if photo else '<div style="font-size:50px;">👤</div>'
            st.markdown(f"""
                <div class="crew-card {card_class}">
                    {img_tag}
                    <h3>{member}</h3>
                    <div class="metric-label">이번 주 / 지난 주</div>
                    <div class="metric-value">{m_this_dist:.1f}km / {m_last_dist:.1f}km</div>
                    <div class="metric-label">7일 평균 페이스</div>
                    <div class="metric-value">{pace_str}</div>
                    <div class="metric-label">연속 휴식일</div>
                    <div class="metric-value">{rest_days}일째</div>
                    <div class="rest-badge" style="background-color: {status_color}">{status_text}</div>
                </div>
            """, unsafe_allow_html=True)

    st.divider()

    # --- 섹션 3: Insight & Fun (복구 완료) ---
    st.header("🏆 Insight & Fun")
    if not this_week.empty:
        i1, i2, i3 = st.columns(3)
        with i1:
            best_d = this_week.loc[this_week["distance"].idxmax()]
            st.subheader("🏃 이 주의 마라토너")
            st.info(f"**{best_d['runner']}**\n\n한 번에 {best_d['distance']:.1f}km를 달렸습니다!")
        with i2:
            best_e = this_week.loc[this_week["elevation"].idxmax()]
            st.subheader("⛰️ 이 주의 등산가")
            st.warning(f"**{best_e['runner']}**\n\n누적 {best_e['elevation']:.0f}m를 올랐습니다!")
        with i3:
            this_week['tmp_pace'] = this_week['duration_sec'] / this_week['distance']
            best_p = this_week[this_week['tmp_pace'] > 0].loc[this_week['tmp_pace'].idxmin()]
            st.subheader("⚡ 이 주의 폭주기관차")
            st.success(f"**{best_p['runner']}**\n\n최고 페이스 {int(best_p['tmp_pace']//60)}'{int(best_p['tmp_pace']%60)}\" 기록!")
    else:
        st.info("이번 주 활동 데이터가 수집되면 랭킹이 표시됩니다. 크루원들을 독려해 주세요!")

    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
