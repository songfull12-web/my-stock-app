import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 페이지 설정
st.set_page_config(page_title="Technical Alpha V4.0", layout="wide")

# 1. 한글 종목명 -> 코드 변환용 마스터 데이터 로드 (KRX)
# 한글 종목명 -> 코드 변환용 마스터 데이터 (수정 버전)
@st.cache_data
def load_krx_data():
    try:
        # 더 안정적인 정보제공 사이트(GitHub 등)의 KRX 종목 리스트 활용
        url = 'http://kind.krx.co.kr/corpofficial/corpList.do?method=download'
        # 가끔 보안 설정 때문에 header를 추가해야 할 수도 있습니다.
        df = pd.read_html(url, header=0)[0]
        df = df[['회사명', '종목코드']]
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        return df
    except Exception as e:
        # 데이터 로딩 실패 시 에러 메시지 출력 (디버깅용)
        st.sidebar.error(f"데이터 로딩 실패: {e}")
        return pd.DataFrame(columns=['회사명', '종목코드'])


krx_list = load_krx_data()

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 트레이딩 터미널")
    user_input = st.text_input("종목명 또는 티커 입력", value="삼성전자").strip()
    
    ticker = user_input.upper()
    if not user_input.isdigit() and not any(ext in ticker for ext in ['.KS', '.KQ']):
        match = krx_list[krx_list['회사명'] == user_input]
        if not match.empty:
            ticker = f"{match['종목코드'].values[0]}.KS"
            st.success(f"🇰🇷 확인: {user_input} ({ticker})")
        else:
            ticker = user_input.upper()
    elif user_input.isdigit():
        ticker = f"{user_input}.KS"

    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=1)
    st.divider()
    show_guide = st.checkbox("매수/손절 가이드 표시", value=True)

# 2. 선형 회귀 채널 계산 함수
def calculate_channel(df):
    y = df['Close'].values
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std_dev = np.std(y - base)
    return base, base + (std_dev * 2), base - (std_dev * 2)

# 메인 분석 로직
if ticker:
    try:
        df = yf.download(ticker, period=period, auto_adjust=True)
        
        if df.empty and ".KS" in ticker:
            ticker = ticker.replace(".KS", ".KQ")
            df = yf.download(ticker, period=period, auto_adjust=True)

        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            
            curr_p = float(df['Close'].iloc[-1])
            high_v = float(df['High'].max())
            low_v = float(df['Low'].min())
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"))

            base, upper, lower = calculate_channel(df)
            fig.add_trace(go.Scatter(x=df['Date'], y=upper, name="저항선", line=dict(color='#f87171', width=1, dash='dash')))
            fig.add_trace(go.Scatter(x=df['Date'], y=lower, name="지지선", line=dict(color='#4ade80', width=1, dash='dash')))

            # 4. 수평 피보나치 (일직선 보정)
            diff = high_v - low_v
            fib_ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
            fib_colors = ["#475569", "#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#475569"]
            
            for r, c in zip(fib_ratios, fib_colors):
                price_level = high_v - (r * diff)
                fig.add_hline(y=price_level, line_dash="dot", line_color=c, 
                             annotation_text=f"Fib {r*100}% ({price_level:,.0f})", 
                             annotation_position="bottom right")

            fig.update_layout(title=f"<b>{user_input}</b> 분석 센터", template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            if show_guide:
                st.subheader("🎯 실시간 전략 가이드")
                sup_p, res_p = lower[-1], upper[-1]
                stop_l = sup_p * 0.97
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if curr_p <= sup_p * 1.03: st.success(f"**매수 적기!** 지지선(${sup_p:,.0f}) 부근")
                    elif curr_p >= res_p * 0.95: st.warning("**과열!** 매수 주의")
                    else: st.info("**관망 구간**")
                with c2:
                    st.error(f"**손절가: {stop_l:,.0f}**")
                    st.info(f"**목표가: {res_p:,.0f}**")
                with c3:
                    st.write(f"현재가: **{curr_p:,.0f}**")
        else:
            st.error("종목을 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"오류: {e}")
