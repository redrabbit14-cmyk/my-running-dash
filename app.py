import streamlit as st
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
import google.generativeai as genai

# Google Gemini API 설정 (secrets.toml에서 불러오기)
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
    AI_AVAILABLE = True
except:
    AI_AVAILABLE = False
    st.warning("🤖 AI 코치: API 키를 확인해주세요 (.streamlit/secrets.toml)")

# 크루 프로필 이미지 (깃허브 URL)
PROFILE_IMAGES = {
    "용남": "https://github.com/redrabbit14-cmyk/my-running-dash/raw/main/images/%EC%9A%A9%EB%82%A8.jpg",
    "주현": "https://github.com/redrabbit14-cmyk/my-running-dash/raw/main/images/%EC%A3%BC%ED%98%84.jpg",
    "유재": "https://github.com/redrabbit14-cmyk/my-running-dash/raw/main/images/%EC%9C%A0%EC%9E%AC.jpg",
    "재탁": "https://github.com/redrabbit14-cmyk/my-running-dash/raw/main/images/%EC%9E%AC%ED%83%81.jpg",
}

# 1. 페이지 설정
st.set_page_config(page_title="러닝 크루 대시보드", page_icon="🏃", layout="wide")

# 2. 전체 스타일 (배경, 카드 정리)
st.markdown("""
    <style>
    /* 전체 배경 톤 살짝 넣기 */
    .stApp {
        background-color: #f5f7fb;
    }

    /* 기본 텍스트 톤 조정 */
    h1, h2, h3, h4, h5, h6 {
        color: #222831;
    }

    /* 공통 카드 스타일 */
    .crew-card {
        border-radius: 16px;
        padding: 18px;
        text-align: center;
        background-color: #ffffff;
        box-shadow: 0 3px 10px rgba(15, 23, 42, 0.06);
        margin-bottom: 18px;
        border: 1px solid #e5e7eb;
    }

    /* 상태별 상단 바 + 연한 배경색 */
    .status-good {
        border-top: 8px solid #22c55e;
        background: linear-gradient(180deg, #ecfdf3 0%, #ffffff 40%);
    }
    .status-warning {
        border-top: 8px solid #facc15;
        background: linear-gradient(180deg, #fef9c3 0%, #ffffff 40%);
    }
    .status-danger {
        border-top: 8px solid #ef4444;
        background: linear-gradient(180deg, #fee2e2 0%, #ffffff 40%);
    }

    .metric-label {
        font-size: 0.80rem;
        color: #6b7280;
        margin-top: 10px;
    }
    .metric-value {
        font-size: 1.15rem;
        font-weight: 600;
        color: #111827;
        margin-bottom: 4px;
    }
    .profile-img {
        border-radius: 50%;
        object-fit: cover;
        width: 86px;
        height: 86px;
        border: 3px solid #e5e7eb;
        margin-bottom: 6px;
    }

    /* AI 코치 카드 */
    .ai-coach-card {
        border-radius: 16px;
        padding: 18px;
        text-align: left;
        background: linear-gradient(135deg, #4f46e5 0%, #6366f1 40%, #a855f7 100%);
        box-shadow: 0 4px 14px rgba(88, 28, 135, 0.35);
        margin-bottom: 18px;
        color: #f9fafb;
        border: 1px solid rgba(191, 219, 254, 0.4);
    }
    .ai-coach-card h3 {
        margin-top: 0;
        margin-bottom: 6px;
        color: #f9fafb;
    }

    /* 모바일에서 위아래 여백 살짝 줄이기 */
    @media (max-width: 768px) {
        .crew-card {
            padding: 14px;
        }
        .ai-coach-card {
            padding: 14px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# "HH:MM:SS" 또는 "MM:SS" 텍스트를 초로 변환
def parse_time_to_seconds(time_str: str) -> int:
    if not time_str or time_str == "0":
        return 0
    try:
        parts = str(time_str).strip().split(":")
        if len(parts) == 3:      # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:    # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        else:
            return int(parts[0]) if parts[0].isdigit() else 0
    except:
        return 0

@st.cache_data(ttl=600)
def get_notion_data() -> pd.DataFrame:
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
    DATABASE_ID = os.environ.get("DATABASE_ID")

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    all_pages = []
    has_more = True
    next_cursor = None

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
            # 러너(선택)
            name = p.get("러너", {}).get("select", {}).get("name", "")

            # 실제 거리(수식 number)
            dist_val = p.get("실제 거리", {}).get("number")
            if dist_val is None:
                dist_val = p.get("실제 거리", {}).get("formula", {}).get("number", 0)

            # 날짜
            date_str = p.get("날짜", {}).get("date", {}).get("start", "")

            # 시간(텍스트)
            time_rich_text = p.get("시간", {}).get("rich_text", [])
            time_text = (
                time_rich_text[0].get("text", {}).get("content", "0")
                if time_rich_text else "0"
            )

            # 고도(숫자)
            elev = p.get("고도", {}).get("number", 0) or 0

            if name and date_str:
                records.append({
                    "runner": name,
                    "date": pd.to_datetime(date_str).tz_localize(None),
                    "distance": float(dist_val or 0),
                    "duration_sec": parse_time_to_seconds(time_text),
                    "elevation": elev,
                })
        except:
            continue

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.drop_duplicates(subset=["runner", "date", "distance"], keep="first")
        df = df.sort_values("date", ascending=False)
    return df

# AI 코치 추천 생성
def get_ai_coach_recommendation(member_data: pd.DataFrame, member_name: str) -> str:
    if not AI_AVAILABLE or member_data.empty:
        return f"{member_name}: 데이터 부족으로 가벼운 조깅 20~30분을 추천합니다."
    
    # 최근 7일 데이터
    recent = member_data[member_data["date"] >= (datetime.now() - timedelta(days=7))]
    if recent.empty:
        return f"{member_name}: 최근 7일 활동이 없어, 20~30분 조깅으로 몸을 깨워보세요."

    total_dist = recent["distance"].sum()
    total_time = recent["duration_sec"].sum()
    avg_pace = total_time / total_dist if total_dist > 0 else 0
    
    days_active = len(recent[recent["distance"] > 0])
    rest_days = 7 - days_active
    
    prompt = f"""
    러너 {member_name}의 최근 7일 데이터:
    - 총 거리: {total_dist:.1f}km
    - 평균 페이스(초/킬로): {avg_pace:.1f}
    - 활동일: {days_active}일 (휴식일: {rest_days}일)

    위 정보를 바탕으로 {member_name}에게 맞는 러닝 훈련을 1~2줄 한국어로 추천해줘.
    예시는 "가볍게 조깅 30분 + 스트라이드 5회" 처럼, 구체적인 세션 형태로.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return f"{member_name}: AI 분석 중 오류가 발생해, 오늘은 기분 좋은 조깅을 추천합니다."

def main():
    # 최상단 제목
    st.header("🏃 러닝 크루 대시보드")

    df = get_notion_data()
    if df.empty:
        st.info("데이터를 불러오는 중입니다...")
        return

    # 오늘 기준 주간
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6, hours=23, minutes=59)
    last_mon = mon - timedelta(days=7)
    last_sun = mon - timedelta(seconds=1)

    this_week = df[(df["date"] >= mon) & (df["date"] <= sun)]
    last_week = df[(df["date"] >= last_mon) & (df["date"] <= last_sun)]

    # 섹션 1: 크루 현황
    st.subheader("📊 크루 현황")
    tw_total = this_week["distance"].sum()
    lw_total = last_week["distance"].sum()
    diff = tw_total - lw_total

    c1, c2, c3 = st.columns(3)
    c1.metric("이번 주 크루 총합", f"{tw_total:.1f} km")
    c2.metric("지난 주 크루 총합", f"{lw_total:.1f} km")
    c3.metric(
        "전주 대비 증감",
        f"{diff:+.1f} km",
        delta=f"{((diff / lw_total * 100) if lw_total > 0 else 0):.1f}%"
    )

    st.divider()

    # 섹션 2: 크루 컨디션 체크
    st.subheader("💪 크루 컨디션 체크")
    crew_members = ["재탁", "유재", "주현", "용남"]
    cols = st.columns(len(crew_members))

    for idx, member in enumerate(crew_members):
        m_all = df[df["runner"] == member]
        m_this_dist = this_week[this_week["runner"] == member]["distance"].sum()
        m_last_dist = last_week[last_week["runner"] == member]["distance"].sum()

        # 최근 7일 평균 페이스
        m_7d = m_all[m_all["date"] >= (datetime.now() - timedelta(days=7))]
        pace_display = "0'0\""
        if not m_7d.empty and m_7d["distance"].sum() > 0:
            avg_sec_per_km = m_7d["duration_sec"].sum() / m_7d["distance"].sum()
            pace_display = f"{int(avg_sec_per_km // 60)}'{int(avg_sec_per_km % 60)}\""

        # 연속 휴식일
        rest_days = (today - m_all.iloc[0]["date"]).days if not m_all.empty else 0
        if rest_days <= 1:
            card_class = "status-good"
            status_text = "Good 🔥"
        elif rest_days <= 3:
            card_class = "status-warning"
            status_text = "주의 ⚠️"
        else:
            card_class = "status-danger"
            status_text = "휴식필요 💤"

        with cols[idx]:
            photo_url = PROFILE_IMAGES.get(member, "")
            img_tag = (
                f'<img src="{photo_url}" class="profile-img">'
                if photo_url else '👤'
            )
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
                    <div style="margin-top:10px; font-weight:bold;">{status_text}</div>
                </div>
            """, unsafe_allow_html=True)

    st.divider()

    # 섹션 3: Insight & Fun
    st.subheader("🏆 Insight & Fun")
    if not this_week.empty:
        i1, i2, i3 = st.columns(3)
        with i1:
            best_d = this_week.loc[this_week["distance"].idxmax()]
            st.info(f"🏃 **이 주의 마라토너**\n\n**{best_d['runner']}** ({best_d['distance']:.1f}km)")
        with i2:
            best_e = this_week.loc[this_week["elevation"].idxmax()]
            st.warning(f"⛰️ **이 주의 등산가**\n\n**{best_e['runner']}** ({best_e['elevation']:.0f}m)")
        with i3:
            this_week["tmp_pace"] = this_week["duration_sec"] / this_week["distance"]
            valid_p = this_week[this_week["tmp_pace"] > 0]
            if not valid_p.empty:
                best_p = valid_p.loc[valid_p["tmp_pace"].idxmin()]
                st.success(
                    f"⚡ **이 주의 폭주기관차**\n\n"
                    f"**{best_p['runner']}** "
                    f"({int(best_p['tmp_pace']//60)}'{int(best_p['tmp_pace']%60)}\")"
                )
    else:
        st.info("이번 주 활동 데이터가 수집되면 랭킹이 표시됩니다.")

    # AI 코치 섹션
    st.subheader("🤖 AI 코치 훈련추천")
    
    if st.button("🎯 추천받기", type="primary"):
        recommendations = {}
        progress_bar = st.progress(0)
        
        for i, member in enumerate(crew_members):
            member_data = df[df["runner"] == member]
            recommendations[member] = get_ai_coach_recommendation(member_data, member)
            progress_bar.progress((i + 1) / len(crew_members))
        
        st.success("✅ AI 분석 완료!")
        
        cols_rec = st.columns(2)
        for idx, member in enumerate(crew_members):
            with cols_rec[idx % 2]:
                st.markdown(f"""
                    <div class="ai-coach-card">
                        <h3>{member}</h3>
                        <div style="font-size:1.0rem; line-height:1.4;">
                            {recommendations[member]}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
    else:
        st.info("🎯 '추천받기' 버튼을 누르면 각 크루원별 맞춤 훈련을 AI가 추천합니다!")

    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
