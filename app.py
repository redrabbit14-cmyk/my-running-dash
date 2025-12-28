import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일 수정 (사진 꽉 차게 변경 및 디자인 보강)
st.markdown("""
<style>
    .main { background-color: #f9fafb; padding: 10px; }
    .section-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px; }
    .total-distance-card { background: linear-gradient(to bottom right, #ecfdf5, #d1fae5); border: 2px solid #86efac; border-radius: 12px; padding: 20px; text-align: center; }
    /* 1. 사진을 원형 안에 꽉 채우는 설정 */
    .crew-photo { width: 100px; height: 100px; border-radius: 50%; margin: 0 auto 10px; object-fit: cover; border: 3px solid #3b82f6; display: block; }
    .crew-avatar { width: 100px; height: 100px; border-radius: 50%; background: #e5e7eb; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; font-size: 40px; }
    .crew-stat-box { border-radius: 6px; padding: 8px 4px; margin: 4px 0; font-size: 13px; text-align: center; }
    .stat-label { font-size: 11px; color: #6b7280; font-weight: 600; }
    .stat-value { font-size: 15px; font-weight: 700; color: #1f2937; }
</style>
""", unsafe_allow_html=True)

# 3. 페이스 변환 및 계산 함수
def pace_to_seconds(pace_str):
    """'5:30' -> 330초 변환"""
    if not pace_str or ":" not in str(pace_str): return None
    try:
        parts = str(pace_str).split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except: return None

def seconds_to_pace(seconds):
    """330초 -> '5:30' 변환"""
    if seconds is None or seconds <= 0: return "N/A"
    return f"{int(seconds//60)}:{int(seconds%60):02d}"

@st.cache_data(ttl=300)
def fetch_notion_data():
    try:
        response = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers={"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
            json={}
        )
        if not response.ok: return pd.DataFrame()
        
        data = []
        for row in response.json().get("results", []):
            props = row.get("properties", {})
            # 날짜 가져오기
            date_raw = props.get("날짜", {}).get("date", {}).get("start") if props.get("날짜") else None
            if not date_raw: continue
            
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            # 거리 (km 단위 유지)
            dist = 0
            dist_prop = props.get("평균 페이스", {}).get("number", 0) # 실제 거리 속성명 확인 필요
            for k in ["실제 거리", "거리"]:
                if props.get(k, {}).get("number"):
                    dist = props[k]["number"]
                    if dist > 100: dist /= 1000
                    break
            
            # 페이스 가져오기
            pace = "N/A"
            pace_prop = props.get("평균 페이스", {})
            if pace_prop.get("type") == "rich_text" and pace_prop["rich_text"]:
                pace = pace_prop["rich_text"][0]["plain_text"]
            
            # 고도 및 사진
            elev = props.get("고도", {}).get("number", 0) or 0
            photo = None
            if props.get("사진", {}).get("files"):
                f = props["사진"]["files"][0]
                photo = f.get("file", {}).get("url") or f.get("external", {}).get("url")
            
            data.append({"날짜": date_raw, "러너": runner, "거리": dist, "페이스": pace, "고도": elev, "사진": photo})
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜']).dt.tz_localize(None)
            # 2. 중복 제거: 동일 날짜, 동일 러너의 중복 데이터 중 거리나 페이스가 있는 것만 남김
            df = df.sort_values('거리', ascending=False).drop_duplicates(['날짜', '러너'], keep='first')
        return df
    except: return pd.DataFrame()

# --- 메인 로직 ---
df = fetch_notion_data()

if not df.empty:
    st.title("🏃 러닝 크루 대시보드")
    
    # 5. 주간 기준 설정 (일요일~월요일)
    # 오늘이 월요일(0)이면 지난 일요일(-1)부터 오늘까지
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # pandas의 weekday는 월:0 ~ 일:6 / 일요일 기준 주간 시작 계산
    days_since_sunday = (today.weekday() + 1) % 7
    sun_start = today - timedelta(days=days_since_sunday)
    
    # 이번 주 데이터 (일요일 ~ 현재)
    tw = df[df['날짜'] >= sun_start]
    # 지난 주 데이터 (그 전주 일요일 ~ 이번주 일요일 전까지)
    lw_start = sun_start - timedelta(days=7)
    lw = df[(df['날짜'] >= lw_start) & (df['날짜'] < sun_start)]
    
    # 상단 총거리 표시 (일~월 합산)
    total_dist = tw['거리'].sum()
    st.markdown(f'''
        <div class="section-card">
            <div class="total-distance-card">
                <div style="font-size:16px; color:#047857; font-weight:600; margin-bottom:5px;">총거리 (크루 합산)</div>
                <div style="font-size:48px;font-weight:800;color:#047857;">{total_dist:.1f} km</div>
                <div style="font-size:14px;color:#6b7280;">이번 주 일요일부터 현재까지 기록</div>
            </div>
        </div>
    ''', unsafe_allow_html=True)

    # 크루 컨디션
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:18px; font-weight:700; margin-bottom:15px;">👥 크루 컨디션</div>', unsafe_allow_html=True)
    
    crew_members = ["재택", "웅남", "주현", "유재"] # 표시 순서 고정
    cols = st.columns(4)
    
    for idx, member in enumerate(crew_members):
        m_tw = tw[tw['러너'] == member]
        m_lw = lw[lw['러너'] == member]
        
        dist = m_tw['거리'].sum()
        # 페이스 평균 계산 (초 단위 변환 후 평균 내고 다시 문자열로)
        m_tw['p_sec'] = m_tw['페이스'].apply(pace_to_seconds)
        avg_p_sec = m_tw['p_sec'].mean() if not m_tw['p_sec'].dropna().empty else None
        avg_pace = seconds_to_pace(avg_p_sec)
        
        photo = df[df['러너'] == member].sort_values('날짜', ascending=False)['사진'].dropna().iloc[0] if not df[df['러너'] == member]['사진'].dropna().empty else None
        
        with cols[idx]:
            # 1. 사진 꽉 채우기 스타일 적용
            if photo: st.markdown(f'<img src="{photo}" class="crew-photo">', unsafe_allow_html=True)
            else: st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align:center; font-weight:700; margin-bottom:10px;">{member}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="crew-stat-box" style="background:#dbeafe;"><div class="stat-label">주간 거리</div><div class="stat-value">{dist:.1f}km</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="crew-stat-box" style="background:#f3e8ff;"><div class="stat-label">평균 페이스</div><div class="stat-value">{avg_pace}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 4. Insights (최고 스피드 러너 수정)
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:18px; font-weight:700; margin-bottom:15px;">🏆 Insights & Fun</div>', unsafe_allow_html=True)
    
    if not tw.empty:
        # 최장 거리
        top_d = tw.groupby('러너')['거리'].sum()
        st.markdown(f'<div style="margin-bottom:8px;">🥇 이번 주 최장 거리: <b>{top_d.idxmax()} ({top_d.max():.1f}km)</b></div>', unsafe_allow_html=True)
        
        # 최고 스피드 (가장 낮은 초 단위 페이스 찾기)
        tw['p_sec'] = tw['페이스'].apply(pace_to_seconds)
        valid_tw = tw[tw['p_sec'] > 120] # 2분 페이스 미만은 데이터 오류로 간주 제외
        if not valid_tw.empty:
            fastest_idx = valid_tw['p_sec'].idxmin()
            fastest_runner = valid_tw.loc[fastest_idx, '러너']
            fastest_pace = valid_tw.loc[fastest_idx, '페이스']
            st.markdown(f'<div>⚡ 이번 주 최고 스피드: <b>{fastest_runner} ({fastest_pace}/km)</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
