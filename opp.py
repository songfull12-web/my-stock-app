import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Technical Analysis Center", layout="wide")

# 2. 한글 종목 데이터 로드 (안정적인 데이터 소스 사용)
@st.cache_data
def load_master_data():
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Name', 'Symbol']].rename(columns={'Name':'회사명', 'Symbol':'종목코드'})
    except:
        return pd.DataFrame(columns=['회사명', '종목코드'])

master_df = load_master_data()

# 3. 사이드바 - 스마트 검색 시스템
with st.sidebar:
    st.header("🔍 종목 검색")
    # 검색 키워드 입력 (예: 삼성, 하이닉스)
    keyword = st.text_input("종목명 일부 입력", value="삼성전자").strip()
    
    final_ticker = ""
    
    if keyword:
        # 입력어가 포함된 모든 한국 종목 찾기
        matches = master_df[master_df['회사명'].str.contains(keyword, na=False, case=False)]
        
        if not matches.empty:
            st.info(f"🔎 '{keyword}' 관련 종목을 찾았습니다.")
            # 드롭다운 선택 메뉴 생성
            options = [f"{row['회사명']} ({row['종목코드']})" for _, row in matches.iterrows()]
            selected_item = st.selectbox("분석할 종목을 선택하세요", options)
            
            if selected_item:
                code = selected_item.split('(')[1].replace(')', '')
                # 한국 주식 티커 형식 완성
                final_ticker = f"{code}.KS"
        else:
            # 한글 결과가 없으면 미국 티커로 간주
            final_ticker = keyword.upper()
            st.warning(f"💡 한국 종목이 없어 미국 티커 '{final_ticker}'로 시도합니다.")

    st.divider()
    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=1)
    show_channel = st.checkbox("회귀 채널(추세선) 표시", value=True)
    show_fib = st.checkbox("피보나치 채널(색상) 표시", value=True)

# 4. 분석 계산 엔진
def run_analysis(df):
    y = df['Close'].values.flatten()
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std = np.std(y - base)
    return base, base + (std * 2), base - (std * 2)

# 5. 메인 화면 출력
if final_ticker:
    try:
        # 데이터 호출
        data = yf.download(final_ticker, period=period, auto_adjust=True)
        # 한국 주식의 경우 코스피에서 안 나오면 코스닥으로 재시도
        if data.empty and ".KS" in final_ticker:
            data = yf.download(final_ticker.replace(".KS", ".KQ"), period=period, auto_adjust=True)

        if not data.empty:
            # MultiIndex 정리
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            
            # 주요 수치 추출
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            
            # 차트 그리기
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], 
                                         low=data['Low'], close=data['Close'], name="주가"))

            # 회귀 채널 (추세선)
            if show_channel:
                base, upper, lower = run_analysis(data)
                fig.add_trace(go.Scatter(x=data['Date'], y=upper, name="저항선", line=dict(color='#f87171', width=2, dash='dash')))
                fig.add_trace(go.Scatter(x=data['Date'], y=lower, name="지지선", line=dict(color='#4ade80', width=2, dash='dash')))

            # 피보나치 채널 (구역 색상 강화)
            if show_fib:
                diff = high_v - low_v
                ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                colors = ['rgba(255,0,0,0.1)', 'rgba(255,165,0,0.1)', 'rgba(255,255,0,0.1)', 
                          'rgba(0,255,0,0.1)', 'rgba(0,0,255,0.1)', 'rgba(128,0,128,0.1)']
                for i in range(len(ratios)-1):
                    y0, y1 = high_v - (ratios[i] * diff), high_v - (ratios[i+1] * diff)
                    fig.add_hrect(y0=y0, y1=y1, fillcolor=colors[i], line_width=0)
                    fig.add_hline(y=y0, line_width=1, line_color="white", opacity=0.1)

            fig.update_layout(title=f"<b>{final_ticker}</b> 분석 리포트", template="plotly_dark", height=750, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 하단 실시간 전략 가이드 부활
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
                if show_channel:
                    if curr_p <= lower[-1] * 1.02: st.success("🎯 매수 적기: 지지선 근접")
                    elif curr_p >= upper[-1] * 0.98: st.warning("⚠️ 매수 주의: 저항선 근접")
            with c2:
                if show_channel: st.metric("목표가 (저항선)", f"{upper[-1]:,.0f}")
            with c3:
                if show_channel: st.metric("손절가 (지지선 하단)", f"{lower[-1] * 0.97:,.0f}")
        else:
            st.error("데이터를 불러올 수 없습니다. 종목명이나 티커를 다시 확인하세요.")
    except Exception as e:
        st.error(f"시스템 오류: {e}")
