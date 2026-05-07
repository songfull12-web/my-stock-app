import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Technical Analysis Center", layout="wide")

# 2. 한글 종목명 데이터 로드 (안정성 강화)
@st.cache_data
def load_master():
    try:
        # 경로 1: KRX 공식
        url = 'https://kind.krx.co.kr/corpofficial/corpList.do?method=download'
        df = pd.read_html(url, header=0)[0][['회사명', '종목코드']]
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        return df
    except:
        try:
            # 경로 2: 백업 데이터
            url_bak = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
            df_bak = pd.read_csv(url_bak)
            return df_bak[['Name', 'Symbol']].rename(columns={'Name':'회사명', 'Symbol':'종목코드'})
        except:
            return pd.DataFrame(columns=['회사명', '종목코드'])

master_df = load_master()

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 설정")
    # 메인 입력창
    user_input = st.text_input("종목명 또는 티커 입력", value="005930.KS").strip()
    
    # --- 한글 검색 도우미 추가 ---
    st.divider()
    st.subheader("💡 종목코드 찾기 (한글 전용)")
    search_name = st.text_input("한글 주식 이름을 입력하세요", placeholder="예: 삼성전자")
    
    ticker = user_input.upper()
    
    if search_name:
        match = master_df[master_df['회사명'].str.contains(search_name, na=False)]
        if not match.empty:
            st.write("✅ 검색 결과 (복사해서 위 입력창에 넣으세요):")
            for i, row in match.iterrows():
                # 코스피(.KS) 기준으로 우선 표시
                st.code(f"{row['종목코드']}.KS", language=None)
        else:
            st.warning("일치하는 종목이 없습니다.")
    st.divider()

    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=1)
    show_channel = st.checkbox("회귀 채널 표시", value=True)
    show_fib = st.checkbox("피보나치 채널 표시", value=True)

# 4. 분석 계산 함수
def get_analysis(df):
    y = df['Close'].values.flatten()
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std = np.std(y - base)
    return base, base + (std * 2), base - (std * 2)

# 5. 메인 차트 출력
if ticker:
    try:
        data = yf.download(ticker, period=period, auto_adjust=True)
        # 데이터가 없을 경우 코스닥(.KQ)으로 재시도
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
                base, upper, lower = get_analysis(data)
                fig.add_trace(go.Scatter(x=data['Date'], y=upper, name="저항선", line=dict(color='#f87171', width=2, dash='dash')))
                fig.add_trace(go.Scatter(x=data['Date'], y=lower, name="지지선", line=dict(color='#4ade80', width=2, dash='dash')))

            # 피보나치 채널 (강화 버전)
            if show_fib:
                diff = high_v - low_v
                ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                colors = ['rgba(255, 0, 0, 0.1)', 'rgba(255, 165, 0, 0.1)', 'rgba(255, 255, 0, 0.1)', 
                          'rgba(0, 128, 0, 0.1)', 'rgba(0, 0, 255, 0.1)', 'rgba(128, 0, 128, 0.1)']
                for i in range(len(ratios)-1):
                    y0, y1 = high_v - (ratios[i] * diff), high_v - (ratios[i+1] * diff)
                    fig.add_hrect(y0=y0, y1=y1, fillcolor=colors[i], line_width=0)
                    fig.add_hline(y=y0, line_width=1, line_color="white", opacity=0.3)
                    fig.add_annotation(x=data['Date'].iloc[0], y=y0, text=f"Fib {ratios[i]*100}%", showarrow=False, xanchor="left")

            fig.update_layout(title=f"<b>{ticker}</b> 분석 결과", template="plotly_dark", height=750, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 매수/매도/손절 가이드
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
                if show_channel and curr_p <= lower[-1] * 1.02: st.success("🎯 매수 적기")
            with c2:
                if show_channel: st.metric("목표가(채널상단)", f"{upper[-1]:,.0f}")
            with c3:
                if show_channel: st.metric("손절가(채널하단)", f"{lower[-1]:,.0f}")
        else:
            st.error("종목을 찾을 수 없습니다. 아래 '종목코드 찾기'에서 코드를 검색해 보세요.")
    except Exception as e:
        st.error(f"오류 발생: {e}")
