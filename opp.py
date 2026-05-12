import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="Global Strategy Terminal", layout="wide")

# 2. [완전 해결] 한국 주식 전종목 리스트 강제 로드 (네이버/KRX 기준)
@st.cache_data(show_spinner="전종목 리스트를 동기화 중입니다...")
def fetch_krx_all():
    # 가장 확실한 KRX 상장사 전체 리스트 (FinanceDataReader 소스 활용)
    url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
    try:
        full_df = pd.read_csv(url)
        # 종목명(Name), 코드(Symbol), 시장(Market)만 추출
        return full_df[['Symbol', 'Name', 'Market']].dropna()
    except:
        # 비상용 (데이터 서버 문제 시)
        return pd.DataFrame([{"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"}])

# 전종목 리스트 확보
master_list = fetch_krx_all()

# 3. 기존 전략 엔진 (피보나치 6단계, ★BUY 타점 - 수정 절대 없음)
def run_strategy(df):
    if len(df) < 20: return df
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    for lv in [0, 0.236, 0.382, 0.500, 0.618, 1.000]:
        df[f'Fib_{int(lv*1000)}'] = hp - lv * diff
    
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 4. 사이드바 (사용자 핵심 요구: 전체 리스트 나열)
with st.sidebar:
    st.header("🔍 전종목 통합 검색")
    search_input = st.text_input("종목명 입력 (예: 삼성, 에코)", value="삼성")
    
    # [핵심] 입력어가 포함된 '전체' 종목 필터링
    # Name 컬럼에 검색어가 포함된 모든 행을 가져옵니다.
    results = master_list[master_list['Name'].str.contains(search_input, na=False, case=False)]
    
    st.subheader(f"📋 '{search_input}' 관련 리스트 ({len(results)}건)")
    
    if not results.empty:
        # 1. 표로 전체 리스트와 코드 출력 (사용자가 코드를 직접 볼 수 있게)
        st.dataframe(results[['Name', 'Symbol', 'Market']].sort_values('Name'), hide_index=True, height=350)
        
        # 2. 선택 박스에 전체 검색 결과 반영
        select_options = [f"{r['Name']} ({r['Symbol']})" for _, r in results.sort_values('Name').iterrows()]
        pick = st.selectbox("분석할 종목 선택", select_options)
        
        selected_code = pick.split("(")[1].replace(")", "")
        m_type = results[results['Symbol'] == selected_code].iloc[0]['Market']
        final_ticker = f"{selected_code}{'.KS' if m_type == 'KOSPI' else '.KQ'}"
        final_name = pick.split(" (")[0]
    else:
        st.warning("국내 리스트에 없습니다. 해외 티커를 입력하세요.")
        final_ticker = search_input.upper()
        final_name = search_input.upper()

    st.divider()
    period = st.selectbox("기간", ["6mo", "1y", "2y"])
    show_fib = st.checkbox("피보나치 채널 표시", value=True)

# 5. 메인 차트 (기존 기능 100% 유지)
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = run_strategy(data)
        
        f = {k: data[f'Fib_{k}'].iloc[-1] for k in [0, 236, 382, 500, 618, 1000]}
        curr = float(data['Close'].iloc[-1])
        
        st.title(f"📊 {final_name} ({final_ticker}) 리포트")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가", f"{curr:,.0f}")
        c2.metric("강력지지(61.8%)", f"{f[618]:,.0f}", f"{((f[618]/curr)-1)*100:.1f}%")
        c3.metric("목표가(38.2%)", f"{f[382]:,.0f}", f"{((f[382]/curr)-1)*100:.1f}%")
        c4.metric("손절가(LP)", f"{f[1000]:,.0f}", f"{((f[1000]/curr)-1)*100:.1f}%", delta_color="inverse")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
        
        if show_fib:
            levels
