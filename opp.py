import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Professional Analysis Pro", layout="wide")

# 2. 종목 리스트 (내장형 + 서버 백업)
@st.cache_data
def get_stock_dict():
    stocks = {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS", "에코프로": "086520.KQ"}
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        for _, row in df.iterrows():
            stocks[row['Name']] = row['Symbol']
    except:
        pass
    return stocks

stock_dict = get_stock_dict()

# 3. 사이드바 검색 및 지표 설정
with st.sidebar:
    st.header("🔍 분석 설정")
    search_input = st.text_input("종목명 입력 (예: 삼성, 에코)", value="삼성전자").strip()
    
    final_ticker = ""
    if search_input:
        matches = [name for name in stock_dict.keys() if search_input in name]
        if matches:
            selected_name = st.selectbox(f"'{search_input}' 검색 결과", matches)
            code = stock_dict[selected_name]
            final_ticker = f"{code}.KS" if code.isdigit() else code
        else:
            final_ticker = search_input.upper()

    st.divider()
    period = st.selectbox("기간", ["6mo", "1y", "2y", "5y"], index=1)
    
    st.subheader("📊 지표 활성화")
    show_ma = st.checkbox("이동평균선 (20일/60일)", value=True)
    show_rsi = st.checkbox("RSI (상대강도지수)", value=True)
    show_fib = st.checkbox("피보나치 채널", value=True)

# 4. 보조지표 계산 함수
def add_indicators(df):
    # 이동평균선
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def get_regression(df):
    y = df['Close'].values.flatten()
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std = np.std(y - base)
    return base, base + (std * 2), base - (std * 2)

# 5. 메인 차트 출력
if final_ticker:
    try:
        data = yf.download(final_ticker, period=period, auto_adjust=True)
        if data.empty and ".KS" in final_ticker:
            data = yf.download(final_ticker.replace(".KS", ".KQ"), period=period, auto_adjust=True)

        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            data = add_indicators(data)
            
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            
            # 서브플롯 생성 (RSI가 있을 경우 2단 차트)
            rows = 2 if show_rsi else 1
            row_heights = [0.7, 0.3] if show_rsi else [1.0]
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=row_heights)

            # 1단: 캔들차트 & 추세선
            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], 
                                         low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

            # 이동평균선 추가
            if show_ma:
                fig.add_trace(go.Scatter(x=data['Date'], y=data['MA20'], name="20일선", line=dict(color='yellow', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=data['MA60'], name="60일선", line=dict(color='orange', width=1)), row=1, col=1)

            # 회귀 추세선
            base, upper, lower = get_regression(data)
            fig.add_trace(go.Scatter(x=data['Date'], y=upper, name="상단저항", line=dict(color='#f87171', width=1.5, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['Date'], y=lower, name="하단지지", line=dict(color='#4ade80', width=1.5, dash='dash')), row=1, col=1)

            # 피보나치 (배경)
            if show_fib:
                diff = high_v - low_v
                ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                colors = ['rgba(255,0,0,0.1)', 'rgba(255,165,0,0.1)', 'rgba(255,255,0,0.1)', 'rgba(0,255,0,0.1)', 'rgba(0,0,255,0.1)', 'rgba(128,0,128,0.1)']
                for i in range(len(ratios)-1):
                    y0, y1 = high_v - (ratios[i] * diff), high_v - (ratios[i+1] * diff)
                    fig.add_hrect(y0=y0, y1=y1, fillcolor=colors[i], line_width=0, row=1, col=1)

            # 2단: RSI
            if show_rsi:
                fig.add_trace(go.Scatter(x=data['Date'], y=data['RSI'], name="RSI", line=dict(color='#a78bfa', width=2)), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

            fig.update_layout(title=f"<b>{final_ticker}</b> 종합 기술 분석", template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 실시간 가이드
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
                if curr_p <= lower[-1] * 1.02: st.success("🎯 매수 적기 (추세 하단)")
            with c2:
                st.metric("목표가", f"{upper[-1]:,.0f}")
                if show_rsi and data['RSI'].iloc[-1] > 70: st.error("⚠️ 과매수 구간 (매도 검토)")
            with c3:
                st.metric("손절가", f"{lower[-1] * 0.97:,.0f}")
                if show_rsi and data['RSI'].iloc[-1] < 30: st.info("🔵 과매도 구간 (반등 대기)")
        else:
            st.error("종목을 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"오류: {e}")
