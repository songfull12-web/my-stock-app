import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 페이지 설정
st.set_page_config(page_title="Technical Alpha V2.1", layout="wide")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 설정")
    ticker_raw = st.text_input("티커/종목코드 입력", value="VOO").upper()
    
    # 한국 주식 처리
    if ticker_raw.isdigit():
        ticker = f"{ticker_raw}.KS" if ticker_raw.startswith(('0', '2', '3')) else f"{ticker_raw}.KQ"
    else:
        ticker = ticker_raw

    period = st.selectbox("분석 기간", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    st.divider()
    show_trend = st.checkbox("자동 추세선", value=True)
    show_fib_channel = st.checkbox("피보나치 채널", value=True)

# 알고리즘 함수
def get_trends(df):
    x = np.arange(len(df))
    slope_h, intercept_h, _, _, _ = linregress(x, df['High'])
    slope_l, intercept_l, _, _, _ = linregress(x, df['Low'])
    return (slope_h * x + intercept_h), (slope_l * x + intercept_l), slope_l, intercept_l

if ticker:
    try:
        df = yf.download(ticker, period=period)
        if df.empty:
            st.error("데이터를 불러올 수 없습니다.")
        else:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))

            res_line, sup_line, slope, intercept = get_trends(df)

            if show_trend:
                fig.add_trace(go.Scatter(x=df['Date'], y=res_line, name="저항선", line=dict(color='#f87171', width=1, dash='dash')))
                fig.add_trace(go.Scatter(x=df['Date'], y=sup_line, name="지지선", line=dict(color='#4ade80', width=1, dash='dash')))

            if show_fib_channel:
                x_idx = np.arange(len(df))
                base = slope * x_idx + intercept
                max_d = (df['High'] - base).max()
                for r, c in zip([0.236, 0.382, 0.5, 0.618, 0.786, 1.0], ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#94a3b8']):
                    fig.add_trace(go.Scatter(x=df['Date'], y=base + (max_d * r), name=f"Fib {r*100}%", line=dict(color=c, width=0.8, dash='dot')))

            fig.update_layout(title=f"<b>{ticker}</b> 분석", template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("현재가", f"{float(df['Close'].iloc[-1]):,.2f}")
            c2.metric("기간 고점", f"{float(df['High'].max()):,.2f}")
            c3.metric("기간 저점", f"{float(df['Low'].min()):,.2f}")
    except Exception as e:
        st.error(f"오류: {e}")
