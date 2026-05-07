import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Technical Analysis Center", layout="wide")

# 2. 종목 마스터 데이터 로드 (KRX 전체 리스트)
@st.cache_data
def load_full_master():
    try:
        # 가장 안정적인 경로인 GitHub 데이터를 사용합니다.
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Name', 'Symbol']].rename(columns={'Name':'회사명', 'Symbol':'종목코드'})
    except:
        # 실패 시 빈 데이터프레임 반환
        return pd.DataFrame(columns=['회사명', '종목코드'])

master_df = load_full_master()

# 3. 사이드바 - 지능형 검색
with st.sidebar:
    st.header("🔍 종목 검색")
    search_q = st.text_input("종목명 입력 (예: 삼성, 하이닉스, 에코)", value="삼성전자").strip()
    
    selected_ticker = ""
    
    if search_q:
        # 입력한 글자가 포함된 모든 종목 검색
        matches = master_df[master_df['회사명'].str.contains(search_q, na=False, case=False)]
        
        if not matches.empty:
            st.write(f"🔎 '{search_q}' 검색 결과:")
            # 검색 결과 리스트 생성
            display_list = [f"{row['회사명']} ({row['종목코드']})" for _, row in matches.iterrows()]
            # 사용자가 리스트에서 선택
            choice = st.selectbox("분석할 종목을 선택하세요", display_list)
            
            if choice:
                # 선택된 종목에서 코드 추출 및 티커 생성
                code = choice.split('(')[1].replace(')', '')
                selected_ticker = f"{code}.KS"
        else:
            # 한글 검색 결과가 없으면 미국 티커로 간주
            selected_ticker = search_q.upper()
            st.info(f"💡 미국 티커 '{selected_ticker}'로 분석을 시도합니다.")

    st.divider()
    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=1)
    show_channel = st.checkbox("회귀 채널 표시", value=True)
    show_fib = st.checkbox("피보나치 채널(색상) 표시", value=True)

# 4. 분석 계산 함수
def get_analysis(df):
    y = df['Close'].values.flatten()
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std = np.std(y - base)
    return base, base + (std * 2), base - (std * 2)

# 5. 메인 차트 출력
if selected_ticker:
    try:
        data = yf.download(selected_ticker, period=period, auto_adjust=True)
        # 한국 주식의 경우 코스피/코스닥 재시도
        if data.empty and ".KS" in selected_ticker:
            selected_ticker = selected_ticker.replace(".KS", ".KQ")
            data = yf.download(selected_ticker, period=period, auto_adjust=True)

        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            
            # 차트 구성
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], 
                                         low=data['Low'], close=data['Close'], name="주가"))

            if show_channel:
                base, upper, lower = get_analysis(data)
                fig.add_trace(go.Scatter(x=data['Date'], y=upper, name="저항선", line=dict(color='#f87171', width=2, dash='dash')))
                fig.add_trace(go.Scatter(x=data['Date'], y=lower, name="지지선", line=dict(color='#4ade80', width=2, dash='dash')))

            if show_fib:
                diff = high_v - low_v
                ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                colors = ['rgba(255,0,0,0.1)', 'rgba(255,165,0,0.1)', 'rgba(255,255,0,0.1)', 
                          'rgba(0,255,0,0.1)', 'rgba(0,0,255,0.1)', 'rgba(128,0,128,0.1)']
                for i in range(len(ratios)-1):
                    y0, y1 = high_v - (ratios[i] * diff), high_v - (ratios[i+1] * diff)
                    fig.add_hrect(y0=y0, y1=y1, fillcolor=colors[i], line_width=0)
                    fig.add_hline(y=y0, line_width=1, line_color="white", opacity=0.2)

            fig.update_layout(title=f"<b>{selected_ticker}</b> 상세 분석", template="plotly_dark", height=750, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 매수/매도 가이드
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
                if show_channel and curr_p <= lower[-1] * 1.02: st.success("🎯 매수 적기")
            with c2:
                if show_channel: st.metric("목표가(채널상단)", f"{upper[-1]:,.0f}")
            with c3:
                if show_channel: st.metric("손절가(채널하단)", f"{lower[-1] * 0.97:,.0f}")
        else:
            st.error("데이터를 찾을 수 없습니다. 종목명이나 티커를 다시 확인하세요.")
    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")
