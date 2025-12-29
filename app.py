import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import requests

# 1. 환경 설정
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="러닝 크루 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS 스타일
st.markdown("""
<style>
    .main { background-color: #f9fafb; padding: 10px; }
    .section-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px; }
    .total-distance-card { background: linear-gradient(to bottom right, #ecfdf5, #d1fae5); border: 2px solid #86efac; border-radius: 12px; padding: 20px; text-align: center; }
    .crew-photo { width: 100px; height: 100px; border-radius: 50%; margin: 0 auto 10px; object-fit: cover; border: 3px solid #3b82f6; display: block; }
    .crew-avatar { width: 100px; height: 100px; border-radius: 50%; background: #e5e7eb; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; font-size: 40px; }
    .crew-stat-box { border-radius: 8px; padding: 8px 4px; margin: 5px 0; font-size: 12px; text-align: center; min-height: 50px; display: flex; flex-direction: column; justify-content: center; }
    .stat-label { font-size: 10px; color: #6b7280; font-weight: 600; margin-bottom: 2px; }
    .stat-value { font-size: 14px; font-weight: 700; color: #1f2937; }
</style>
""", unsafe_allow_html=True)

# 3. 유틸리티 함수
def mps_to_pace_str(mps):
    """스트라바 m/s 숫자를 '분:초' 문자열로 변환"""
    try:
        if mps is None or mps <= 0:
            return "N/A"
        # 1000m 이동에 걸리는 초 계산
        total_seconds = 1000 / mps
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        return f"{minutes}:{seconds:02d}"
    except:
        return "N/A"

def pace_to_seconds(pace_str):
    """'분:초' 페이스 문자열을 계산용 초 단위로 변환"""
    try:
        if not pace_str or pd.isna(pace_str) or pace_str == "N/A":
            return None
        pace_str = str(pace_str).strip()
        # 다양한 구분자 대응
        pace_str = pace_str.replace("'", ":").replace('"', "").replace("’", ":").replace("´", ":")
        if ":" not in pace_str:
            return None
        parts = pace_str.split(':')
        if len(parts) != 2:
            return None
        minutes = float(parts[0].strip())
        seconds = float(parts[1].strip())
        return int(minutes * 60 + seconds)
    except:
        return None

def seconds_to_pace(seconds):
    """평균 초 단위를 다시 '분:초' 문자열로 변환"""
    if seconds is None or pd.isna(seconds) or seconds <= 0:
        return "N/A"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"

@st.cache_data(ttl=300)
def fetch_notion_data():
    """노션 데이터베이스에서 데이터 가져오기"""
    try:
        response = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            json={"page_size": 100}
        )
        
        if not response.ok:
            st.error(f"노션 API 오류: {response.status_code}")
            return pd.DataFrame()
        
        data = []
        for row in response.json().get("results", []):
            props = row.get("properties", {})
            
            # 날짜 추출
            date_obj = props.get("날짜", {}).get("date", {})
            if not date_obj or not date_obj.get("start"):
                continue
            date_str = date_obj.get("start")[:10]
            
            # 러너 추출
            runner_obj = props.get("러너", {}).get("select")
            runner = runner_obj.get("name", "Unknown") if runner_obj else "Unknown"
            
            # 거리 추출
            distance = 0
            for field_name in ["실제 거리", "거리", "Distance"]:
                dist_val = props.get(field_name, {}).get("number")
                if dist_val is not None:
                    distance = dist_val if dist_val < 100 else dist_val / 1000
                    break
            
            # 페이스 추출 (숫자형 '페이스' 컬럼에서 m/s를 읽어 변환)
            mps_val = props.get("페이스", {}).get("number")
            pace = mps_to_pace_str(mps_val)
            
            # 고도 추출
            elevation = props.get("고도", {}).get("number", 0) or 0
            
            # 사진 추출
            photo_url = None
            files_field = props.get("사진", {}).get("files", [])
            if files_field and len(files_field) > 0:
                file_obj = files_field[0]
                if file_obj.get("type") == "file":
                    photo_url = file_obj.get("file", {}).get("url")
                elif file_obj.get("type") == "external":
                    photo_url = file_obj.get("external", {}).get("url")
            
            created_time = row.get("created_time", "")
            
            data.append({
                "날짜": date_str,
                "러너": runner,
                "거리": distance,
                "페이스": pace,
                "고도": elevation,
                "사진": photo_url,
                "생성시간": created_time
            })
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['날짜'] = pd.to_datetime(df['날짜'])
        df['생성시간'] = pd.to_datetime(df['생성시간'])
        
        # 중복 제거 및 필터링
        df = df.sort_values(['날짜', '러너', '생성시간'], ascending=[True, True, False])
        df = df.drop_duplicates(subset=['날짜', '러너'], keep='first')
        df = df[df['거리'] > 0]
        
        return df
    
    except Exception as e:
        st.error(f"데이터 로딩 오류: {str(e)}")
        return pd.DataFrame()

# --- 메인 실행 ---
df = fetch_notion_data()

if df.empty:
    st.warning("⚠️ 노션 데이터를 불러올 수 없습니다.")
    st.stop()

st.title("🏃 러닝 크루 대시보드")

# 주간 기준 설정
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
days_since_sunday = (today.weekday() + 1) % 7
this_week_start = today - timedelta(days=days_since_sunday)
last_week_start = this_week_start - timedelta(days=7)

tw = df[df['날짜'] >= this_week_start].copy()
lw = df[(df['날짜'] >= last_week_start) & (df['날짜'] < this_week_start)].copy()

# 1. 상단 총거리 카드
tw_total = tw['거리'].sum()
lw_total = lw['거리'].sum()
st.markdown(f'''
    <div class="section-card">
        <div class="total-distance-card">
            <div style="font-size:16px; color:#047857; font-weight:600; margin-bottom:5px;">총거리 (크루 합산)</div>
            <div style="font-size:48px;font-weight:800;color:#047857;">{tw_total:.2f} km</div>
            <div style="font-size:14px;color:#6b7280;">이번 주 일요일부터 현재까지 | 지난주 전체: {lw_total:.1f} km</div>
        </div>
    </div>
''', unsafe_allow_html=True)

# 2. 크루 컨디션 섹션
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div style="font-size:18px; font-weight:700; margin-bottom:15px;">👥 크루 컨디션</div>', unsafe_allow_html=True)

crew_list = ["용남", "재탁", "주현", "유재"]
cols = st.columns(4)

for idx, member in enumerate(crew_list):
    with cols[idx]:
        m_tw = tw[tw['러너'] == member].copy()
        m_lw = lw[lw['러너'] == member].copy()
        m_all = df[df['러너'] == member].copy()
        
        tw_dist = m_tw['거리'].sum()
        lw_dist = m_lw['거리'].sum()
        
        if lw_dist > 0:
            change_pct = ((tw_dist - lw_dist) / lw_dist) * 100
        else:
            change_pct = 0 if tw_dist == 0 else 100
        
        # 평균 페이스 계산 로직
        if not m_all.empty:
            m_all_sorted = m_all.sort_values('날짜', ascending=False)
            recent_runs = m_all_sorted.head(7)
            recent_runs['페이스_초'] = recent_runs['페이스'].apply(pace_to_seconds)
            valid_paces = recent_runs['페이스_초'].dropna()
            avg_pace_str = seconds_to_pace(valid_paces.mean()) if len(valid_paces) > 0 else "N/A"
        else:
            avg_pace_str = "N/A"
        
        # 휴식일 계산
        if not m_all.empty:
            last_run_date = m_all['날짜'].max()
            rest_days = max(0, (today - last_run_date).days)
        else:
            rest_days = 0
        
        # 프로필 사진 설정
        photo_url = None
        if not m_all.empty:
            recent_photos = m_all.sort_values('날짜', ascending=False)['사진'].dropna()
            if len(recent_photos) > 0:
                photo_url = recent_photos.iloc[0]
        
        if photo_url:
            st.markdown(f'<img src="{photo_url}" class="crew-photo">', unsafe_allow_html=True)
        else:
            st.markdown('<div class="crew-avatar">👤</div>', unsafe_allow_html=True)
        
        st.markdown(f'<div style="text-align:center; font-weight:700; margin-bottom:10px;">{member}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="crew-stat-box" style="background:#f0f9ff;"><div class="stat-label">이번주 / 지난주</div><div class="stat-value">{tw_dist:.2f} / {lw_dist:.1f}km</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="crew-stat-box" style="background:#f0fdf4;"><div class="stat-label">전주 대비</div><div class="stat-value">{change_pct:+.1f}%</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="crew-stat-box" style="background:#f5f3ff;"><div class="stat-label">평균 페이스</div><div class="stat-value">{avg_pace_str}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="crew-stat-box" style="background:#fffbeb;"><div class="stat-label">연속 휴식일</div><div class="stat-value">{rest_days}일</div></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# 3. Insights 섹션
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div style="font-size:18px; font-weight:700; margin-bottom:15px;">🏆 Insights & Fun</div>', unsafe_allow_html=True)

if not tw.empty:
    # 이번 주 최장 거리
    top_dist = tw.groupby('러너')['거리'].sum()
    if not top_dist.empty:
        st.markdown(f'<div style="margin-bottom:8px;">🥇 이번 주 최장 거리: <b>{top_dist.idxmax()} ({top_dist.max():.2f}km)</b></div>', unsafe_allow_html=True)
    
    # 이번 주 최고 고도
    top_elev = tw.groupby('러너')['고도'].sum()
    if not top_elev.empty and top_elev.max() > 0:
        st.markdown(f'<div style="margin-bottom:8px;">⛰️ 이번 주 최고 고도: <b>{top_elev.idxmax()} ({top_elev.max():.0f}m)</b></div>', unsafe_allow_html=True)
    
    # 이번 주 최고 스피드 (최저 페이스)
    tw_copy = tw.copy()
    tw_copy['페이스_초'] = tw_copy['페이스'].apply(pace_to_seconds)
    valid_sp = tw_copy[tw_copy['페이스_초'].notnull()]
    if not valid_sp.empty:
        fastest_idx = valid_sp['페이스_초'].idxmin()
        fastest = valid_sp.loc[fastest_idx]
        st.markdown(f'<div>⚡ 이번 주 최고 스피드: <b>{fastest["러너"]} ({fastest["페이스"]}/km)</b></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
