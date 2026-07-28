import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import uuid

# 페이지 설정
st.set_page_config(page_title="팀 예산 관리 시스템", page_icon="📊", layout="wide")

# --- Google Sheets 연결 세팅 ---
# Streamlit Cloud의 Secrets 기능을 사용해 보안 정보를 불러옵니다.
@st.cache_resource
def init_connection():
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=10) # 10초마다 캐시 갱신 (다중 사용자 환경 고려)
def get_data():
    try:
        client = init_connection()
        sheet = client.open_by_url(st.secrets["gsheets_url"]).sheet1
        records = sheet.get_all_records()
        if not records:
            return sheet, pd.DataFrame(columns=["ID", "날짜", "팀원", "항목", "금액"])
        return sheet, pd.DataFrame(records)
    except Exception as e:
        st.error(f"Google Sheets 연결에 실패했습니다: {e}")
        st.stop()

# 데이터 불러오기
sheet, df = get_data()

# --- 헤더 ---
st.markdown("<h1 style='text-align: center;'>📊 팀 예산 관리 시스템</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>부장님 보고용 월별 예산 취합 및 대시보드</p>", unsafe_allow_html=True)
st.write("---")

# --- 탭 구성 ---
tab1, tab2 = st.tabs(["📝 데이터 입력", "📈 전체 대시보드"])

# --- TAB 1: 데이터 입력 ---
with tab1:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("📝 내역 입력")
        with st.form("budget_form", clear_on_submit=True):
            member = st.selectbox("팀원 선택", ["부장님", "팀원1", "팀원2", "팀원3", "팀원4"])
            
            # 현재 연-월을 기본값으로 하는 날짜 입력
            current_month = datetime.now().strftime("%Y-%m")
            month = st.text_input("해당 월 (YYYY-MM 형식)", value=current_month)
            
            category = st.selectbox("예산 항목", ["수선유지비", "비품", "개량공사"])
            amount = st.number_input("사용 금액 (원)", min_value=0, step=1000)
            
            submit_button = st.form_submit_button(label="기록 저장하기", use_container_width=True)
            
            if submit_button:
                if amount > 0:
                    new_row = [str(uuid.uuid4())[:8], month, member, category, amount]
                    try:
                        # 시트에 데이터 추가 (헤더가 첫 줄에 있다고 가정)
                        sheet.append_row(new_row)
                        st.success("✅ 예산 데이터가 정상적으로 기록되었습니다.")
                        st.cache_data.clear() # 캐시 초기화하여 새로고침 유도
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 중 오류 발생: {e}")
                else:
                    st.warning("금액은 0원보다 커야 합니다.")
                    
    with col2:
        st.subheader("📂 최근 입력 내역")
        if not df.empty:
            # 테이블 가독성을 위해 최신순으로 정렬 후 금액 포맷팅
            display_df = df.copy()
            display_df = display_df.iloc[::-1] # 역순 (최신이 위로)
            display_df['금액'] = display_df['금액'].apply(lambda x: f"{int(x):,}원")
            
            st.dataframe(
                display_df[["날짜", "팀원", "항목", "금액"]], 
                use_container_width=True, 
                hide_index=True
            )
            
            if st.button("🚨 모든 데이터 초기화 (위험)", type="secondary"):
                # 헤더만 남기고 데이터 모두 삭제
                sheet.resize(1)
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("등록된 데이터가 없습니다.")

# --- TAB 2: 전체 대시보드 ---
with tab2:
    if df.empty:
        st.warning("데이터가 없어 대시보드를 표시할 수 없습니다. 먼저 데이터를 입력해주세요.")
    else:
        # 데이터 타입 변환 방어코드
        df['금액'] = pd.to_numeric(df['금액'], errors='coerce').fillna(0)
        
        # 1. 요약 지표 (Metrics)
        total_amount = df['금액'].sum()
        top_category = df.groupby('항목')['금액'].sum().idxmax()
        top_category_amount = df.groupby('항목')['금액'].sum().max()
        data_count = len(df)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("전체 누적 사용액", f"{int(total_amount):,}원")
        m2.metric("최대 사용 항목", f"{top_category}", f"{int(top_category_amount):,}원 사용", delta_color="off")
        m3.metric("데이터 건수", f"{data_count}건")
        
        st.write("---")
        
        # 2. 차트 (Charts)
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🏠 항목별 예산 분포")
            cat_df = df.groupby('항목', as_index=False)['금액'].sum()
            fig_pie = px.pie(cat_df, values='금액', names='항목', hole=0.4, 
                             color_discrete_sequence=['#3b82f6', '#10b981', '#8b5cf6'])
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c2:
            st.subheader("👥 팀원별 누적 사용액")
            mem_df = df.groupby('팀원', as_index=False)['금액'].sum()
            fig_bar = px.bar(mem_df, x='팀원', y='금액', text_auto='.2s', 
                             color_discrete_sequence=['#60a5fa'])
            fig_bar.update_traces(textposition='outside')
            st.plotly_chart(fig_bar, use_container_width=True)
            
        # 3. 월별/항목별 요약 테이블 (Pivot Table)
        st.subheader("📅 월별/항목별 요약 테이블 (취합본)")
        pivot_df = pd.pivot_table(df, values='금액', index='날짜', columns='항목', aggfunc='sum', fill_value=0)
        pivot_df['합계'] = pivot_df.sum(axis=1)
        pivot_df = pivot_df.sort_index(ascending=False) # 최신 월이 위로 오게
        
        # 스타일링 및 콤마 포맷팅
        st.dataframe(
            pivot_df.style.format("{:,.0f}"), 
            use_container_width=True
        )
