import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="Custom Trading Terminal", layout="wide")

# 2. 전종목 데이터베이스 확보 (네이버/KRX 기준 절대 누락 방지)
@st.cache_data
def load_krx_all():
    try:
        # 한국거래소 전체 종목 데이터 소스
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Symbol', 'Name', 'Market']]
    except:
        # 비상용 기본 데이터
        return pd.DataFrame([{"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"}])

all_data = load_krx_all()

# 3. 전략 엔진: 피보나치 + 타점 (사용자 요구 지표 100% 구현)
def calculate_strategy(df):
    if len(df) < 20: return df
    
    # 지표 계산: 이평선 및 RSI
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 피보나치 6단계 계산 (HP/LP 기준)
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    levels = [0, 0.236, 0.382, 0.5, 0.618, 1]
    for lv in levels:
        df[f'Fib_{int(lv*1000)}'] = hp - lv * diff
    
    # ★BUY 타점 로직
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 4. 사이드바: 종목 검색 및 코드 나열
with st.sidebar:
    st.header("🔍 종목 검색")
    search_word = st.text_input("종목명 일부 입력 (예: 삼성, 현대)", value="삼성")
    
    # [핵심] 검색어가 포함된 모든 종목 나열 (네이버 스타일)
    results = all_data[all_data['Name'].str.contains(search_word, na=False, case=False)]
    
    if not results.empty:
        st.subheader(f"📋 '{search_word}' 검색 결과 ({len(results)}건)")
        # 표로 이름, 코드, 시장 노출 (여기서 티커 바로 확인 가능)
        st.dataframe(results[['Name', 'Symbol', 'Market']].sort_values('Name'), hide_index=True, height=350)
        
        # 선택 박스
        selected = st.selectbox("분석할 종목 선택", [f"{r['Name']} ({r['Symbol']})" for _, r in results.iterrows()])
        
        ticker_raw = selected.split("(")[1].replace(")", "")
        m_type = results[results['Symbol'] == ticker_raw].iloc[0]['Market']
        final_ticker = f"{ticker_raw}{'.KS' if m_type == 'KOSPI' else '.KQ'}"
        final_name = selected.split(" (")[0]
    else:
        st.info("국내 결과 없음 -> 해외 티커 모드")
        final_ticker = search_word.upper()
        final_name = search_word.upper()

    st.divider()
    period = st.selectbox("기간", ["6mo", "1y", "2y"], index=0)
    show_fib = st.checkbox("피보나치 채널 표시", value=True)

# 5. 메인 차트 및 전략 가이드 리포트
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = calculate_strategy(data)
        
        # 피보나치 수치 및 현재가
        curr = float(data['Close'].iloc[-1])
        f = {k: data[f'Fib_{k}'].iloc[-1] for k in [0, 236, 382, 500, 618, 1000]}
        
        st.title(f"📊 {final_name} ({final_ticker}) 전략")
        
        # 상단 메트릭 가이드
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가", f"{curr:,.0f}")
        c2.metric("강력지지(61.8%)", f"{f[618]:,.0f}", f"{((f[618]/curr)-1)*100:.1f}%")
        c3.metric("수익목표(38.2%)", f"{f[236]:,.0f}", f"{((f[236]/curr)-1)*100:.1f}%")
        c4.metric("손절가(LP)", f"{f[1000]:,.0f}", f"{((f[1000]/curr)-1)*100:.1f}%", delta_color="inverse")

        # 차트 생성
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
        
        # 피보나치 색상 채널
        if show_fib:
            levels = [(0, 236, 'red'), (236, 382, 'orange'), (382, 500, 'yellow'), (500, 618, 'green'), (618, 1000, 'blue')]
            for t, b, color in levels:
                fig.add_trace(go.Scatter(x=data['Date'], y=[f[t]]*len(data), line=dict(width=0), showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=[f[b]]*len(data), fill='tonexty', fillcolor=f'rgba({color_map[color] if "color_map" in globals() else "128,128,128"},0.1)', line=dict(width=0.5, color='rgba(255,255,255,0.1)'), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['Date'], y=[f[618]]*len(data), name="GOLDEN LINE", line=dict(color='gold', width=4)), row=1, col=1)

        # 캔들스틱 및 ★BUY 타점
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        buy_data = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buy_data['Date'], y=buy_data['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buy_data), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='매수타점'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='gray'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
