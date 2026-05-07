import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 페이지 설정
st.set_page_config(page_title="Technical Alpha V2.0", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #020617; }
    .stMetric { background-color: #0f172a; border-radius: 10px; padding: 15px; border: 1px solid #1e293b; }
    </style>
    """, unsafe_allow_html=True)

st.title("📈 Technical Alpha V2.0")
st.caption("자동 추세선 & 피보나치 채널 & 한국/미국 통합 분석")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 설정")
    ticker_raw = st.text_input("티커/종목코드 입력", value="VOO").upper()
    
    # 한국 주식 판별 및 처리
    if ticker_raw.isdigit():
        # 삼성전자(005930) 같은 숫자 코드인 경우
        if ticker_raw.startswith(('0', '2', '3')): # 대략적인 코스피/코스닥 구분 시도
            ticker = f"{ticker_raw}.KS"
        else:
            ticker = f"{ticker_raw}.KQ"
        st.info(f"K-주식 인식: {ticker}")
    else:
        ticker = ticker_raw

    period = st.selectbox("분석 기간", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    
    st.divider()
    st.subheader("표시 설정")
    show_trend = st.checkbox("자동 추세선 (Support/Resist)", value=True)
    show_fib_channel = st.checkbox("자동 피보나치 채널", value=True)
    show_fib_retracement = st.checkbox("피보나치 되돌림 (Horizontal)", value=False)

# --- 알고리즘 함수 ---

def get_pivot_trendlines(df):
    """선형 회귀를 이용한 자동 추세선 계산"""
    x = np.arange(len(df))
    # 저항선 (고점 연결)
    slope_h, intercept_h, r_h, _, _ = linregress(x, df['High'])
    # 지지선 (저점 연결)
    slope_l, intercept_l, r_l, _, _ = linregress(x, df['Low'])
    return (slope_h * x + intercept_h), (slope_l * x + intercept_l), slope_l, intercept_l

def calculate_fib_channels(df, slope, intercept):
    """추세선 기울기를 바탕으로 피보나치 채널 평행선 계산"""
    x = np.arange(len(df))
    base_line = slope * x + intercept
    
    # 채널의 폭 계산 (가장 먼 고점과의 거리)
    distances = df['High'] - base_line
    max_dist = distances.max()
    
    # 피보나치 비율
    ratios = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    fib_lines = {}
    for r in ratios:
        fib_lines[f"{r*100}%"] = base_line + (max_dist * r)
    
    return fib_lines, base_line + max_dist

# --- 메인 실행 로직 ---

if ticker:
    try:
        with st.spinner('데이터 분석 중...'):
            df = yf.download(ticker, period=period)
        
        if df.empty:
            st.warning("데이터를 불러올 수 없습니다. 티커를 확인하세요. (예: 005930)")
        else:
            # 다중 인덱스 처리
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            
            # 수치 추출
            current_price = float(df['Close'].iloc[-1])
            high_all = float(df['High'].max())
            low_all = float(df['Low'].min())
            
            fig = go.Figure()

            # 1. 캔들스틱
            fig.add_trace(go.Candlestick(
                x=df['Date'], open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name="Price"
            ))

            # 2. 자동 추세선 및 채널 계산
            res_line, sup_line, slope, intercept = get_pivot_trendlines(df)

            if show_trend:
                fig.add_trace(go.Scatter(x=df['Date'], y=res_line, name="알고리즘 저항", line=dict(color='#f87171', width=1, dash='dash')))
                fig.add_trace(go.Scatter(x=df['Date'], y=sup_line, name="알고리즘 지지", line=dict(color='#4ade80', width=1, dash='dash')))

            if show_fib_channel:
                fib_lines, top_line = calculate_fib_channels(df, slope, intercept)
                # 채널 상단 (100%)
                fig.add_trace(go.Scatter(x=df['Date'], y=top_line, name="채널 상단", line=dict(color='#94a3b8', width=1)))
                # 피보나치 내부선
                colors = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899']
                for (name, line_data), color in zip(fib_lines.items(), colors):
                    fig.add_trace(go.Scatter(x=df['Date'], y=line_data, name=f"Fib {name}", line=dict(color=color, width=0.8, dash='dot')))

            if show_fib_retracement:
                diff = high_all - low_all
                ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
                for r in ratios:
                    p = high_all - (r * diff)
                    fig.add_hline(y=p, line_dash="dashdot", line_color="#475569", annotation_text=f"Retrace {r*100}%")

            # 레이아웃 정밀 조정
            fig.update_layout(
                title=f"<b>{ticker}</b> Multi-Dimensional Analysis",
                template="plotly_dark",
                height=800,
                xaxis_rangeslider_visible=False,
                margin=dict(l=50, r=50, t=80, b=50),
                paper_bgcolor="#020617",
                plot_bgcolor="#020617"
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # 핵심 지표 요약
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("현재가", f"{current_price:,.2f}")
            m2.metric("기간 최고가", f"{high_all:,.2f}")
            m3.metric("기간 최저가", f"{low_all:,.2f}")
            m4.metric("변동폭", f"{(high_all-low_all):,.2f}")

    except Exception as e:
        st.error(f"시스템 오류: {e}")

with st.expander("💡 사용 가이드"):
    st.write("""
    - **한국 주식:** 삼성전자는 `005930`, SK하이닉스는 `000660` 처럼 숫자 코드만 입력하세요.
    - **자동 추세선:** 선형 회귀 알고리즘이 전체 데이터의 흐름을 파악하여 지지와 저항을 선으로 표시합니다.
    - **피보나치 채널:** 추세의 기울기를 유지한 채, 황금 비율만큼 이격된 평행 채널을 그려줍니다. 추세장(VOO 등)에서 매우 유용합니다.
    """)

### ✅ 업데이트 적용 방법
1.  **GitHub**에서 `app.py`를 열고 위 코드를 전체 복사해서 붙여넣으세요.
2.  **`requirements.txt`**에 `scipy`가 포함되어 있는지 확인하세요. (없다면 한 줄 추가: `scipy`)
3.  **Streamlit Cloud**에서 새로고침을 하면 약 1분 후 V2.0 시스템이 가동됩니다.

이제 **피보나치 채널**을 통해 단순히 가격이 '얼마'냐를 넘어, '어떤 기울기로 움직이고 있는가'를 한눈에 파악하실 수 있습니다. 영준님의 성공적인 투자를 응원합니다!_
