import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 페이지 설정
st.set_page_config(page_title="Technical Alpha V4.1", layout="wide")

# 1. 한글 종목명 -> 코드 변환 (안정적인 대체 경로 사용)
@st.cache_data
def load_krx_data():
    try:
        # 한국거래소(KRX) 상장종목 리스트 대체 주소
        url = 'https://kind.krx.co.kr/corpofficial/corpList.do?method=download'
        # 보안 이슈를 피하기 위해 storage에서 직접 읽어오거나 대체 로직 적용
        df = pd.read_html(url, header=0)[0]
        df = df[['회사명', '종목코드']]
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        return df
    except Exception:
        # 위 주소가 막혔을 때를 대비한 2차 백업 경로 (네이버 금융 등 활용 가능)
        try:
            url_backup = "https://raw.githubusercontent.com/lee-seung-gyu/stock-data-korea/main/stock_codes.csv"
            return pd.read_csv(url_backup, dtype={'종목코드': str})
        except:
            return pd.DataFrame(columns=['회사명', '종목코드'])

krx_list = load_krx_data()

# 2. 사이드바 설정
with st.sidebar:
    st.header("⚙️ 트레이딩 터미널")
    user_input = st.text_input("종목명 또는 티커 입력", value="삼성전자").strip()
    
    ticker = user_input.upper()
    # 한글 검색 처리
    if not user_input.isdigit() and not any(ext in ticker for ext in ['.KS', '.KQ']):
        if not krx_list.empty:
            match = krx_list[krx_list['회사명'] == user_input]
            if not match.empty:
                ticker = f"{match['종목코드'].values[0]}.KS"
                st.success(f"🇰🇷 확인: {user_input} ({ticker})")
            else:
                ticker = user_input.upper() # 미국 주식 시도
        else:
            ticker = user_input.upper()
    elif user_input.isdigit():
        ticker = f"{user_input}.KS"

    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=1)
    st.divider()
    show_guide = st.checkbox("매수/손절 가이드 표시", value=True)

# 3. 분석 함수들
def calculate_channel(df):
    y = df['Close'].values
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std_dev = np.std(y - base)
    return base, base + (std_dev * 2), base - (std_dev * base*0) # 하단 보정

# 메인 실행부
if ticker:
    try:
        df = yf.download(ticker, period=period, auto_adjust=True)
        
        # 코스피/코스닥 자동 전환
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
            
            # 차트
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"))

            # 회귀 채널
            base, upper, lower = calculate_channel(df)
            fig.add_trace(go.Scatter(x=df['Date'], y=upper, name="저항선", line=dict(color='#f87171', width=1, dash='dash')))
            fig.add_trace(go.Scatter(x=df['Date'], y=lower, name="지지선", line=dict(color='#4ade80', width=1, dash='dash')))

            # 수평 피보나치
            diff = high_v - low_v
            ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
            colors = ["#475569", "#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#475569"]
            for r, c in zip(ratios, colors):
                level = high_v - (r * diff)
                fig.add_hline(y=level, line_dash="dot", line_color=c, 
                             annotation_text=f"Fib {r*100}%", annotation_position="bottom right")

            fig.update_layout(title=f"<b>{user_input}</b> 분석", template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            if show_guide:
                st.subheader("🎯 전략 가이드")
                sup_p, res_p = lower[-1], upper[-1]
                c1, c2 = st.columns(2)
                with c1:
                    st.info(f"현재가: {curr_p:,.0f} | 목표가: {res_p:,.0f}")
                with c2:
                    st.error(f"손절가(지지선): {sup_p:,.0f}")
        else:
            st.error("데이터를 불러올 수 없습니다. 티커나 이름을 확인하세요.")
    except Exception as e:
        st.error(f"오류 발생: {e}")
