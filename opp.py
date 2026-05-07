import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Technical Analysis Center", layout="wide")

# 2. 한글 종목명 로드
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
    show_fib = st.checkbox("강력 피보나치 채널 표시", value=True)

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
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            
            curr_p = float(data['Close'].iloc[-1])
            high_v = float(data['High'].max())
            low_v = float(data['Low'].min())
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], 
                                         low=data['Low'], close=data['Close'], name="주가"))

            # 회귀 채널
            if show_channel:
                base, upper, lower = get_channel(data)
                fig.add_trace(go.Scatter(x=data['Date'], y=upper, name="채널 상단", line=dict(color='#f87171', width=2, dash='dash')))
                fig.add_trace(go.Scatter(x=data['Date'], y=lower, name="채널 하단", line=dict(color='#4ade80', width=2, dash='dash')))

            # 피보나치 채널 (색상 구역 추가)
            if show_fib:
                diff = high_v - low_v
                ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                colors = ['rgba(255, 0, 0, 0.1)', 'rgba(255, 165, 0, 0.1)', 'rgba(255, 255, 0, 0.1)', 
                          'rgba(0, 128, 0, 0.1)', 'rgba(0, 0, 255, 0.1)', 'rgba(128, 0, 128, 0.1)']
                
                for i in range(len(ratios)-1):
                    y0 = high_v - (ratios[i] * diff)
                    y1 = high_v - (ratios[i+1] * diff)
                    # 수평선 긋기
                    fig.add_hline(y=y0, line_width=1, line_color="white", opacity=0.5)
                    # 구간 색상 채우기
                    fig.add_hrect(y0=y0, y1=y1, fillcolor=colors[i], line_width=0)
                    # 라벨 추가
                    fig.add_annotation(x=data['Date'].iloc[-1], y=y0, text=f"Fib {ratios[i]*100}%", showarrow=False, xanchor="left")
                
                fig.add_hline(y=high_v - diff, line_width=1, line_color="white", opacity=0.5)

            fig.update_layout(title=f"<b>{user_input}</b> 분석 센터", template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 하단 가이드 수치
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
                if show_channel:
                    if curr_p <= lower[-1] * 1.02: st.success("🎯 매수 적기")
                    elif curr_p >= upper[-1] * 0.98: st.warning("⚠️ 매수 주의")
            with c2:
                if show_channel: st.metric("목표가(채널상단)", f"{upper[-1]:,.0f}")
            with c3:
                if show_channel: st.metric("손절가(채널하단)", f"{lower[-1]:,.0f}")
        else:
            st.error("데이터를 불러올 수 없습니다.")
    except Exception as e:
        st.error(f"오류 발생: {e}")
