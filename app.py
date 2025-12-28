import streamlit as st
from notion_client import Client
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# =====================
# 기본 설정
# =====================
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(
    page_title="러닝 크루 대시보드",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================
# 스타일
# =====================
st.markdown("""
<style>
.main { background-color: #f9fafb; padding: 10px; }
.section-card { background: white; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.section-title { font-size: 20px; font-weight: 700; margin-bottom: 12px; }
.subsection-title { font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.notice-box { background:#eff6ff; border:2px solid #bfdbfe; border-radius:8px; padding:8px; margin-bottom:6px; font-size:13px; }
.weather-card { background:#f0f9ff; border-radius:6px; padding:6px; text-align:center; font-size:11px; }
.total-distance-card { background:#ecfdf5; border-radius:12px; padding:16px; text-align:center; }
.insight-box { background:white; border-left:4px solid; border-radius:8px; padding:12px; margin:6px 0; }
.insight-full { border-color:#10b981; background:#f0fdf4; }
.insight-climb { border-color:#3b82f6; background:#eff6ff; }
.insight-speed { border-color:#a855f7; background:#faf5ff; }
.ai-box { background:#faf5ff; border-radius:12px; padding:16px; }
</style>
""", unsafe_allow_html=True)

# =====================
# Notion 데이터 로드
# =====================
@st.cache_data(ttl=300)
def fetch_notion_data():
    if not NOTION_TOKEN or not DATABASE_ID:
        return pd.DataFrame()

    notion = Client(auth=NOTION_TOKEN)
    response = notion.databases.query(database_id=DATABASE_ID)
    rows = response.get("results", [])

    data = []
    for r in rows:
        props = r["properties"]

        date_val = props.get("날짜", {}).get("date", {}).get("start", "")
        date_val = date_val[:10] if date_val else None

        runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
        dist = props.get("거리", {}).get("number", 0)
        elev = props.get("고도", {}).get("number", 0)

        pace = None
        if props.get("페이스", {}).get("rich_text"):
            pace = props["페이스"]["rich_text"][0]["plain_text"]

        photo = None
        if props.get("사진", {}).get("files"):
            f = props["사진"]["files"][0]
            photo = f.get("file", {}).get("url") or f.get("external", {}).get("url")

        data.append({
            "날짜": pd.to_datetime(date_val) if date_val else None,
            "러너": runner,
            "거리": dist,
            "고도": elev,
            "페이스": pace,
            "사진": photo
        })

    return pd.DataFrame(data)

def week_data(df, weeks_ago=0):
    end = datetime.now() - timedelta(days=weeks_ago * 7)
    start = end - timedelta(days=7)
    return df[(df["날짜"] >= start) & (df["날짜"] < end)]

# =====================
# AI 추천
# =====================
def get_ai_recommendation(crew):
    summary = "\n".join([
        f"- {c['name']}: {c['distance']:.1f}km, 페이스 {c['pace']}, 휴식 {c['rest']}일"
        for c in crew
    ])

    prompt = f"""
당신은 러닝 코치입니다.
다음 크루원에게 1~2줄 훈련 조언을 해주세요.

{summary}
"""

    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"Content-Type": "application/json"},
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}]
        }
    )

    if res.ok:
        return res.json()["content"][0]["text"]
    return "추천 생성 실패"

# =====================
# 데이터 로드
# =====================
df = fetch_notion_data()

# =====================
# 상단 요약
# =====================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 크루 현황</div>', unsafe_allow_html=True)

if not df.empty:
    this_week = week_data(df, 0)
    last_week = week_data(df, 1)

    total = this_week["거리"].sum()
    prev = last_week["거리"].sum()
    diff = ((total - prev) / prev * 100) if prev > 0 else 0

    st.markdown(f"""
    <div class="total-distance-card">
        <h1>{total:.1f} km</h1>
        <p>전주 대비 {diff:+.0f}%</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# =====================
# 크루 카드 (🔥 에러 수정된 핵심 부분)
# =====================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">👥 크루 컨디션</div>', unsafe_allow_html=True)

if not df.empty:
    members = df["러너"].unique()[:4]
    cols = st.columns(len(members))

    crew_for_ai = []

    for idx, m in enumerate(members):
        md = df[df["러너"] == m]
        w = week_data(md, 0)

        dist = w["거리"].sum()
        pace = w["페이스"].dropna().iloc[0] if not w.empty and w["페이스"].notna().any() else "5:30"
        last_run = w["날짜"].max() if not w.empty else None
        rest = (datetime.now() - last_run).days if last_run is not None else 0

        crew_for_ai.append({
            "name": m,
            "distance": dist,
            "pace": pace,
            "rest": rest
        })

        with cols[idx]:
            st.markdown(f"### {m}")
            st.metric("주간 거리", f"{dist:.1f}km")
            st.metric("평균 페이스", f"{pace}/km")
            st.metric("휴식일", f"{rest}일")

    st.session_state["crew_for_ai"] = crew_for_ai

st.markdown("</div>", unsafe_allow_html=True)

# =====================
# AI 추천
# =====================
st.markdown('<div class="section-card ai-box">', unsafe_allow_html=True)
st.markdown('<div class="section-title">✨ AI 코치 훈련 추천</div>', unsafe_allow_html=True)

if st.button("추천 받기"):
    if "crew_for_ai" in st.session_state:
        with st.spinner("AI 분석 중..."):
            st.session_state["ai_result"] = get_ai_recommendation(st.session_state["crew_for_ai"])

if "ai_result" in st.session_state:
    st.markdown(
        f"<div style='white-space:pre-wrap'>{st.session_state['ai_result']}</div>",
        unsafe_allow_html=True
    )

st.markdown("</div>", unsafe_allow_html=True)
