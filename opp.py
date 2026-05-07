import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Pro Analysis Terminal", layout="wide")

# 2. 종목 리스트 (서버 오류 대비 내장형)
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

# 3. 사이드바 검색
with st.sidebar:
    st.header("🔍 스마트 검색")
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
            st.warning("미국 티커로 분석합니다.")

    st.divider()
    period = st.selectbox("기간", ["6mo", "1y", "2y", "5y"], index=1)
    show_fib = st.checkbox("피보나치 채널(색상강화) 표시", value=True)

# 4. 분석 함수
def get_channel(df):
    y = df['Close'].values.flatten()
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std = np.std(y - base)
    return base, base + (std * 2), base - (std * 2)

# 5. 메인 차트
if final_ticker:
    try:
        data = yf.download(final_ticker, period=period, auto_adjust=True)
        if data.empty and ".KS" in final_ticker:
            data = yf.download(final_ticker.replace(".KS", ".KQ"), period=period, auto_adjust=True)

        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            
            fig = go.Figure()
            # 캔들차트
            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], 
                                         low=data['Low'], close=data['Close'], name="주가"))

            # 피보나치 채널 (강화된 색상 구역)
            if show_fib:
                diff = high_v - low_v
                ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                # 구역별로 명확한 색상 구분
                colors = ['rgba(255,0,0,0.15)', 'rgba(255,165,0,0.15)', 'rgba(255,255,0,0.15)', 
                          'rgba(0,255,0,0.15)', 'rgba(0,0,255,0.15)', 'rgba(128,0,128,0.15)']
                
                for i in range(len(ratios)-1):
                    y0, y1 = high_v - (ratios[i] * diff), high_v - (ratios[i+1] * diff)
                    fig.add_hrect(y0=y0, y1=y1, fillcolor=colors[i], line_width=0)
                    fig.add_hline(y=y0, line_width=1.5, line_color="white", opacity=0.3)
                    fig.add_annotation(x=data['Date'].iloc[0], y=y0, text=f"Fib {ratios[i]*100}%", 
                                     showarrow=False, xanchor="left", font=dict(color="white", size=10))

            fig.update_layout(title=f"<b>{final_ticker}</b> 기술적 분석", template="plotly_dark", height=750, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 매수/매도/손절 가이드 복구
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
                base, upper, lower = get_channel(data)
                if curr_p <= lower[-1] * 1.02: st.success("🎯 매수 적기")
            with c2:
                st.metric("목표가 (저항선)", f"{upper[-1]:,.0f}")
            with c3:
                st.metric("손절가 (지지선)", f"{lower[-1]:,.0f}")
        else:
            st.error("종목을 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"오류: {e}")
