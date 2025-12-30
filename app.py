import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", layout="wide")

@st.cache_data(ttl=300)
def get_notion_data():
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DATABASE_ID = st.secrets["DATABASE_ID"]
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    
    try:
        res = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", headers=headers).json()
        pages = res.get("results", [])
    except:
        return pd.DataFrame()

    records = []
    for page in pages:
        p = page["properties"]
        try:
            # 기본 데이터 추출 (노션 컬럼명과 정확히 일치해야 함)
            name = p.get("러너", {}).get("select", {}).get("name", "")
            date_raw = p.get("날짜", {}).get("date", {}).get("start", "")
            
            # '실제 거리' 가져오기 (숫자 또는 수식 결과값)
            dist_prop = p.get("실제 거리", {})
            distance = 0.0
            if dist_prop.get("type") == "number":
                distance = dist_prop.get("number", 0.0)
            elif dist_prop.get("type") == "formula":
                distance = dist_prop.get("formula", {}).get("number", 0.0)

            if name and date_raw:
                records.append({
                    "runner": name,
                    "date": pd.to_datetime(date_raw).tz_localize(None),
                    "distance": float(distance or 0)
                })
        except:
            continue
    return pd.DataFrame(records)

def main():
    st.title("🏃 러닝 크루 대시보드")
    df = get_notion_data()
    
    if df.empty:
        st.error("노션에서 데이터를 가져오지 못했습니다. Secrets와 컬럼명을 확인해주세요.")
        return

    # --- 데이터 계산 로직 (단순화) ---
    # 오늘 기준 '이번 주 월요일' 찾기
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)

    # 데이터 분류
    this_week_df = df[df["date"] >= this_monday]
    last_week_df = df[(df["date"] >= last_monday) & (df["date"] < this_monday)]

    # --- 1. 크루 현황 출력 ---
    st.header("📊 크루 현황")
    tw_total = this_week_df["distance"].sum()
    lw_total = last_week_df["distance"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 주 총 거리", f"{tw_total:.1f} km")
    c2.metric("지난 주 총 거리", f"{lw_total:.1f} km")
    c3.metric("전주 대비 증감", f"{tw_total - lw_total:+.1f} km")

    st.divider()

    # --- 2. 개인별 현황 ---
    st.header("💪 크루 컨디션 체크")
    runners = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(runners))

    for i, runner in enumerate(runners):
        r_all = df[df["runner"] == runner]
        r_this = this_week_df[this_week_df["runner"] == runner]["distance"].sum()
        r_last = last_week_df[last_week_df["runner"] == runner]["distance"].sum()
        
        with cols[i]:
            with st.container(border=True):
                st.subheader(runner)
                st.write(f"**이번 주:** {r_this:.1f} km")
                st.write(f"**지난 주:** {r_last:.1f} km")
                
                if not r_all.empty:
                    # 가장 최근 런닝일로부터 경과일 계산
                    last_run = r_all.sort_values("date", ascending=False).iloc[0]["date"]
                    days_passed = (today - last_run).days
                    st.info(f"마지막 러닝: {days_passed}일 전")

    if st.button("🔄 데이터 강제 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
