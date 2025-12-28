import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일 (사진 꽉 채우기 및 디자인 유지)
st.markdown("""
<style>
    .main { background-color: #f9fafb; padding: 10px; }
    .section-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px; }
    .total-distance-card { background: linear-gradient(to bottom right, #ecfdf5, #d1fae5); border: 2px solid #86efac; border-radius: 12px; padding: 20px; text-align: center; }
    .crew-photo { width: 90px; height: 90px; border-radius: 50%; margin: 0 auto 10px; object-fit: cover; border: 3px solid #3b82f6; display: block; }
    .crew-avatar { width: 90px; height: 90px; border-radius: 50%; background: #e5e7eb; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; font-size: 40px; }
    .crew-stat-box { border-radius: 6px; padding: 6px 4px; margin: 4px 0; font-size: 12px; text-align: center; }
    .stat-label { font-size: 10px; color: #6b7280; font-weight: 600; }
    .stat-value { font-size: 14px; font-weight: 700; color: #1f2937; }
</style>
""", unsafe_allow_html=True)

# 3. 유틸리티 함수 (페이스 계산 보강)
def pace_to_seconds(pace_str):
    if not pace_str or ":" not in str(pace_str): return None
    try:
        parts = str(pace_str).split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except: return None

def seconds_to_pace(seconds):
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
            date_raw = props.get("날짜", {}).get("date", {}).get("start")
            if not date_raw: continue
            
            runner = props.get("러너", {}).get("select", {}).get("name", "Unknown")
            
            dist = 0
            for k in ["실제 거리", "거리"]:
                if props.get(k, {}).get("number"):
                    dist = props[k]["number"]
                    if dist > 100: dist /= 1000
                    break
            
            pace = "N/A"
            pace_prop = props.get("평균 페이스", {})
            if pace_prop.get("type") == "rich_text" and pace_prop["rich_text"]:
                pace = pace_prop["rich_text"][0]["plain_text"]
            
            elev = props.get("고도", {}).get("number", 0) or 0
            photo = None
            if props.get("사진", {}).get("files"):
                f = props["사진"]["files"][0]
                photo = f.get("file", {}).get("url") or f.get("external", {}).get("url")
            
            data.append({"날짜": date_raw, "러너": runner, "거리": dist, "페이스": pace, "고도": elev, "사진": photo})
        
        df = pd.DataFrame(data)
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜']).dt.tz_localize(None)
            # 중복 제거 (날짜, 러너 기준 가장 긴 기록 유지)
            df = df.sort_values('거리', ascending=False).drop_duplicates(['날짜', '러너'], keep='first')
        return df
    except: return pd.DataFrame()

# --- 메인 실행 ---
df = fetch_notion_data()

if not df.empty:
    st.title("🏃 러닝 크루 대시보드")
    
    # 주간 기준 (일요일 ~ 현재)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_sun = (today.weekday() + 1) % 7
    sun_start = today - timedelta(days=days_since_sun)
    lw_start = sun_start - timedelta(days=7)
    
    tw = df[df['날짜'] >= sun_start]
    lw = df[(df['날짜'] >= lw_start) & (df['날짜'] < sun_start)]
    
    # 1. 상단 총거리
    total_dist = tw['거리'].sum()
    st.markdown(f'''
        <div class="section-card">
            <div class="total-distance-card">
                <div style="font-size:16px; color:#047857; font-weight:600; margin-bottom:5px;">총거리 (크루 합산)</div>
                <div style="font-size:48px;font-weight:800;color:#047857;">{total_dist:.1f} km</div>
                <div style="font-size:14px;color:#6b7280;">이번 주 일요일({sun_start.strftime('%m/%d')})부터 현재까지</div>
            </div>
        </div>
    ''', unsafe_allow_html=True)

    # 2. 크루 컨디션 (성함 수정: 용남, 재탁, 주현, 유재)
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:18px; font-weight:700; margin-bottom:15px;">👥 크루 컨디션</div>', unsafe_allow_html=True)
    
    crew_list = ["용남", "재탁", "주현", "유재"]
    cols = st.columns(4)
    
    for idx, member in enumerate(crew_list):
        m_tw = tw[tw['러너'] == member]
        m_lw = lw[lw['러너'] == member]
        m_all = df[df['러너'] == member].sort_values('날짜', ascending=False)
        
        # 주간 거리 및 전주 대비
        d_val = m_tw['거리'].sum()
        p_val = m_lw['거리'].sum()
        m_change = ((d_val - p_val) / p_val * 100) if p_val > 0 else 0
        
        # 평균 페이스 (초 단위 평균 후 재변환)
        m_tw_copy = m_tw.copy()
        m_tw_copy['p_sec'] = m_tw_copy['페이스'].apply(pace_to_seconds)
        avg_p_sec = m_tw_copy['p_sec'].mean() if not m_tw_copy['p_sec'].dropna().empty else None
        avg_pace = seconds_to_pace(avg_p_sec)
        
        # 연속 휴식일
        last_run = m_all['날짜'].iloc[0] if not m_all.empty else today
        rest_days = (today - last_run).days
        
        photo = m_all['사진'].dropna().iloc[0] if not m_all['사진'].dropna().empty else None
        
        with cols[idx]:
            if photo: st.markdown(f'<img src="{photo}" class="crew-photo">', unsafe_allow_html=True)
            else: st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="text-align:center; font-weight:700; margin-bottom:10px;">{member}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="crew-stat-box" style="background:#dbeafe;"><div class="stat-label">주간 거리</div><div class="stat-value">{d_val:.1f}km</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="crew-stat-box" style="background:#dcfce7;"><div class="stat-label">전주 대비</div><div class="stat-value">{m_change:+.1f}%</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="crew-stat-box" style="background:#f3e8ff;"><div class="stat-label">평균 페이스</div><div class="stat-value">{avg_pace}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="crew-stat-box" style="background:#fef3c7;"><div class="stat-label">연속 휴식일</div><div class="stat-value">{rest_days}일</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 3. Insights & Fun (최고고도, 최고스피드)
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:18px; font-weight:700; margin-bottom:15px;">🏆 Insights & Fun</div>', unsafe_allow_html=True)
    
    if not tw.empty:
        # 최장 거리
        top_d = tw.groupby('러너')['거리'].sum()
        st.markdown(f'<div style="margin-bottom:8px;">🥇 이번 주 최장 거리: <b>{top_d.idxmax()} ({top_d.max():.1f}km)</b></div>', unsafe_allow_html=True)
        
        # 최고 고도
        top_e = tw.groupby('러너')['고도'].sum()
        if top_e.max() > 0:
            st.markdown(f'<div style="margin-bottom:8px;">⛰️ 이번 주 최고 고도: <b>{top_e.idxmax()} ({top_e.max():.0f}m)</b></div>', unsafe_allow_html=True)
        
        # 최고 스피드 (페이스 문자열 -> 초 변환 후 최소값 찾기)
        tw_copy = tw.copy()
        tw_copy['p_sec'] = tw_copy['페이스'].apply(pace_to_seconds)
        valid_sp = tw_copy[tw_copy['p_sec'] > 180] # 3분 페이스 이상만 인정
        if not valid_sp.empty:
            fastest = valid_sp.loc[valid_sp['p_sec'].idxmin()]
            st.markdown(f'<div>⚡ 이번 주 최고 스피드: <b>{fastest["러너"]} ({fastest["페이스"]}/km)</b></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
