import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Technical Analysis Center", layout="wide")

# 2. 한글 종목명 로드 (백업 경로 포함)
@st.cache_data
def load_master():
    try:
        url = 'https://kind.krx.co.kr/corpofficial/corpList.do?method=download'
        df = pd.read_html(url, header=0)[0][['회사명', '종목코드']]
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        return df
    except:
        return pd.DataFrame(columns=['회사명', '종목코드'])

master_df = load_master()

# 3. 사이드바 - 설정
with st.sidebar:
    st.header("🔍 분석 설정")
    user_input = st.text_input("종목명 또는 티커", value="삼성전자").strip()
    
    ticker = user_input.upper()
    if not user_input.isdigit() and not any(ext in ticker for ext in ['.KS', '.KQ']):
        match = master_df[master_df['회사명'] == user_input]
        if not match.empty:
            ticker = f"{match['종목코드'].values[0]}.KS"
            st.success(f"🇰🇷 확인: {ticker}")

    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=1)
    st.divider()
    show_channel = st.checkbox("회귀 채널(추세선) 표시", value=True)
    show_fib = st.checkbox("피보나치 수평선 표시", value=True)

# 4. 분석 계산
def get_channel(df):
    y = df['Close'].values.flatten()
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std = np.std(y - base)
    return base, base + (std * 2), base - (std * 2)

# 5. 메인 출력
if ticker:
    try:
        data = yf.download(ticker, period=period, auto_adjust=True)
        if data.empty and ".KS" in ticker:
            ticker = ticker.replace(".KS", ".KQ")
            data = yf.download(ticker, period=period, auto_adjust=True)

        if not data.empty:
            # MultiIndex 해결
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            
            # 수치 변환 (Series 에러 방지)
            curr_p = float(data['Close'].iloc[-1])
            high_v = float(data['High'].max())
            low_v = float(data['Low'].min())
            
            # 차트 생성
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], 
                                         low=data['Low'], close=data['Close'], name="주가"))

            if show_channel:
                base, upper, lower = get_channel(data)
                fig.add_trace(go.Scatter(x=data['Date'], y=upper, name="저항선", line=dict(color='rgba(255,100,100,0.6)', dash='dash')))
                fig.add_trace(go.Scatter(x=data['Date'], y=lower, name="지지선", line=dict(color='rgba(100,255,100,0.6)', dash='dash')))

            if show_fib:
                diff = high_v - low_v
                for r in [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]:
                    price = high_v - (r * diff)
                    fig.add_hline(y=price, line_dash="dot", line_color="gray", opacity=0.4,
                                 annotation_text=f"Fib {r*100}%", annotation_position="bottom right")

            fig.update_layout(title=f"<b>{user_input} ({ticker})</b> 분석", template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 매수/매도/손절 가이드 복구
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
                if show_channel:
                    if curr_p <= lower[-1] * 1.02: st.success("🎯 매수 적기 (지지선 부근)")
                    elif curr_p >= upper[-1] * 0.98: st.warning("⚠️ 매수 주의 (저항선 부근)")
            with c2:
                if show_channel:
                    st.metric("목표가(매도)", f"{upper[-1]:,.0f}")
                st.write(f"기간 고점: {high_v:,.0f}")
            with c3:
                if show_channel:
                    st.metric("손절가", f"{lower[-1] * 0.97:,.0f}")
                st.write(f"기간 저점: {low_v:,.0f}")
        else:
            st.error("데이터를 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"오류: {e}")
