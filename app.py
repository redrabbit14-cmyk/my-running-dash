import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. CSS: 시안(대시보드_pic.jpg) 스타일 반영
st.markdown("""
    <style>
    .crew-card {
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        background-color: #f8f9fa;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .status-good { border-top: 10px solid #28a745; }
    .status-warning { border-top: 10px solid #ffc107; }
    .status-danger { border-top: 10px solid #dc3545; }
    
    .metric-label { font-size: 0.9rem; color: #666; margin-top: 10px; }
    .metric-value { font-size: 1.4rem; font-weight: bold; color: #333; }
    .rest-days { font-size: 1rem; font-weight: bold; margin-top: 10px; padding: 5px; border-radius: 5px; }
    
    img { border-radius: 50%; object-fit: cover; width: 120px; height: 120px; border: 3px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# 환경 설정 및 데이터 로드 (생략된 fetch/parse 부분은 이전과 동일하되 중복제거 포함)
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}

def time_to_seconds(time_str):
    try:
        parts = list(map(int, str(time_str).split(':')))
        return parts[0]*3600 + parts[1]*60 + parts[2] if len(parts)==3 else parts[0]*60 + parts[1]
    except: return 0

@st.cache_data(ttl=600)
def get_data():
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
            if name and date:
                records.append({"runner": name, "date": date, "distance": float(dist), "duration_sec": time_to_seconds(time_txt), "photo": img})
        except: continue
    df = pd.DataFrame(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df.drop_duplicates(subset=["runner", "date", "distance"])
    return df

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = get_data()
    if df.empty: return

    # 주간 설정
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6, hours=23)
    last_mon = mon - timedelta(days=7)
    last_sun = mon - timedelta(seconds=1)

    # 섹션 1: 크루 현황 (요청하신 대로 유지)
    st.header("📊 크루 현황")
    this_week = df[(df["date"] >= mon) & (df["date"] <= sun)]
    last_week = df[(df["date"] >= last_mon) & (df["date"] <= last_sun)]
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 주 총 거리", f"{this_week['distance'].sum():.1f} km")
    c2.metric("지난 주 총 거리", f"{last_week['distance'].sum():.1f} km")
    c3.metric("전주 대비", f"{this_week['distance'].sum()-last_week['distance'].sum():+.1f} km")

    st.divider()

    # 섹션 2: 크루 컨디션 체크 (시안 디자인 적용)
    st.header("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member].sort_values("date", ascending=False)
        m_this = this_week[this_week["runner"] == member]
        m_last = last_week[last_week["runner"] == member]
        
        # 7일 평균 페이스 (최근 7일 실적 기준)
        seven_days_ago = datetime.now() - timedelta(days=7)
        m_7d = m_all[m_all["date"] >= seven_days_ago]
        
        # 연속 휴식일 계산
        rest_days = (today - m_all.iloc[0]["date"]).days if not m_all.empty else 0
        status_class = "status-good" if rest_days <= 1 else "status-warning" if rest_days <= 3 else "status-danger"
        status_text = "Good 👍" if rest_days <= 1 else "주의 🟡" if rest_days <= 3 else "과부하/휴식필요!"

        with cols[idx]:
            # 카드 시작
            photo = m_all.iloc[0]["photo"] if not m_all.empty and m_all.iloc[0]["photo"] else ""
            img_html = f'<img src="{photo}">' if photo else '👤'
            
            st.markdown(f"""
                <div class="crew-card {status_class}">
                    {img_html}
                    <h3>{member}</h3>
                    <div class="metric-label">이번 주 / 지난 주</div>
                    <div class="metric-value">{m_this['distance'].sum():.1f}km / {m_last['distance'].sum():.1f}km</div>
                    <div class="metric-label">7일 평균 페이스</div>
                    <div class="metric-value">{int((m_7d['duration_sec'].sum()/m_7d['distance'].sum())//60) if not m_7d.empty and m_7d['distance'].sum()>0 else 0}'{int((m_7d['duration_sec'].sum()/m_7d['distance'].sum())%60) if not m_7d.empty and m_7d['distance'].sum()>0 else 0}"</div>
                    <div class="metric-label">연속 휴식일</div>
                    <div class="metric-value">{rest_days}일째</div>
                    <div class="rest-days" style="background-color: {'#d4edda' if rest_days<=1 else '#fff3cd' if rest_days<=3 else '#f8d7da'}">
                        {status_text}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
