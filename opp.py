import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Multi-Timeframe Terminal", layout="wide")

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

# 3. 사이드바 검색 및 상세 설정
with st.sidebar:
    st.header("🔍 분석 설정")
    search_input = st.text_input("종목명 입력 (예: 삼성, 하이닉스)", value="삼성전자").strip()
    
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
    
    # 주기 및 기간 설정 세분화
    st.subheader("⏰ 주기 설정")
    interval = st.selectbox("캔들 주기 (봉 단위)", 
                           ["60m (1시간)", "1d (일봉)", "1wk (주봉)", "1mo (월봉)"], index=1)
    
    # 선택된 주기에 따른 적절한 조회 기간 자동 설정
    default_period = "1mo" if "60m" in interval else "1y"
    period = st.selectbox("조회 범위 (전체 기간)", 
                         ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3 if "1y" == default_period else 0)
    
    interval_code = interval.split(" ")[0]

    st.divider()
    st.subheader("📊 지표 활성화")
    show_ma = st.checkbox("이동평균선 (20/60)", value=True)
    show_rsi = st.checkbox("RSI 지표", value=True)
    show_fib = st.checkbox("피보나치 채널", value=True)

# 4. 분석 계산 함수
def add_indicators(df):
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
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
        # 야후 파이낸스 데이터 호출 (주기 적용)
        data = yf.download(final_ticker, period=period, interval=interval_code, auto_adjust=True)
        if data.empty and ".KS" in final_ticker:
            data = yf.download(final_ticker.replace(".KS", ".KQ"), period=period, interval=interval_code, auto_adjust=True)

        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            data = add_indicators(data)
            
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            
            # 서브플롯 구성
            rows = 2 if show_rsi else 1
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3] if show_rsi else [1.0])

            # 캔들차트
            fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], 
                                         low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

            # 이동평균선
            if show_ma:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA20'], name="20일선", line=dict(color='yellow', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA60'], name="60일선", line=dict(color='orange', width=1)), row=1, col=1)

            # 회귀 추세선 및 피보나치
            base, upper, lower = get_regression(data)
            fig.add_trace(go.Scatter(x=data.iloc[:,0], y=upper, name="저항선", line=dict(color='#f87171', width=1.5, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=data.iloc[:,0], y=lower, name="지지선", line=dict(color='#4ade80', width=1.5, dash='dash')), row=1, col=1)

            if show_fib:
                diff = high_v - low_v
                ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                colors = ['rgba(255,0,0,0.1)', 'rgba(255,165,0,0.1)', 'rgba(255,255,0,0.1)', 'rgba(0,255,0,0.1)', 'rgba(0,0,255,0.1)', 'rgba(128,0,128,0.1)']
                for i in range(len(ratios)-1):
                    y0, y1 = high_v - (ratios[i] * diff), high_v - (ratios[i+1] * diff)
                    fig.add_hrect(y0=y0, y1=y1, fillcolor=colors[i], line_width=0, row=1, col=1)

            # RSI 차트
            if show_rsi:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#a78bfa', width=2)), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

            fig.update_layout(title=f"<b>{final_ticker}</b> ({interval}) 분석", template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 수치 가이드
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
                if curr_p <= lower[-1] * 1.02: st.success("🎯 매수 적기")
            with c2:
                st.metric("목표가", f"{upper[-1]:,.0f}")
            with c3:
                st.metric("손절가", f"{lower[-1] * 0.97:,.0f}")
        else:
            st.error("데이터를 찾을 수 없습니다. (시간별 데이터는 최근 1개월 내만 조회 가능)")
    except Exception as e:
        st.error(f"오류: {e}")
