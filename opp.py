import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Technical Analysis Center", layout="wide")

# 2. 고정 종목 리스트 (서버 오류 시에도 무조건 작동)
@st.cache_data
def get_stock_list():
    # 주요 종목을 내장하여 서버 응답 지연 및 404 에러를 방지합니다.
    data = {
        "삼성전자": "005930.KS", "삼성SDI": "006400.KS", "삼성물산": "028260.KS",
        "삼성바이오로직스": "207940.KS", "삼성전기": "009150.KS", "삼성 SDS": "018260.KS",
        "SK하이닉스": "000660.KS", "현대차": "005380.KS", "기아": "000270.KS",
        "카카오": "035720.KS", "NAVER": "035420.KS", "셀트리온": "068270.KS",
        "에코프로": "086520.KQ", "에코프로비엠": "247540.KQ", "HLB": "028300.KQ"
    }
    # 추가로 깃허브에서 전체 리스트 시도 (실패해도 위 리스트는 유지)
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        for _, row in df.iterrows():
            data[row['Name']] = row['Symbol']
    except:
        pass
    return data

stock_dict = get_stock_list()

# 3. 사이드바 - 지능형 검색 시스템
with st.sidebar:
    st.header("🔍 종목 검색")
    search_input = st.text_input("종목명 입력 (예: 삼성, 하이닉스)", value="삼성전자").strip()
    
    final_ticker = ""
    if search_input:
        # 입력어가 포함된 모든 종목 필터링
        matches = [name for name in stock_dict.keys() if search_input in name]
        
        if matches:
            st.success(f"🔎 '{search_input}' 관련 종목 발견")
            selected_name = st.selectbox("리스트에서 선택하세요", matches)
            code = stock_dict[selected_name]
            # 코드가 숫자만 있으면 .KS 붙이기
            final_ticker = f"{code}.KS" if code.isdigit() else code
        else:
            # 매칭되는 한글이 없으면 미국 티커로 인식
            final_ticker = search_input.upper()
            st.warning(f"💡 미국 주식 '{final_ticker}'로 분석합니다.")

    st.divider()
    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=1)
    show_channel = st.checkbox("회귀 채널 표시", value=True)
    show_fib = st.checkbox("피보나치 채널(색상) 표시", value=True)

# 4. 분석 엔진
def get_analysis(df):
    y = df['Close'].values.flatten()
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std = np.std(y - base)
    return base, base + (std * 2), base - (std * 2)

# 5. 메인 차트 및 가이드 출력
if final_ticker:
    try:
        data = yf.download(final_ticker, period=period, auto_adjust=True)
        # 한국 주식 코스닥 재시도 로직
        if data.empty and ".KS" in final_ticker:
            data = yf.download(final_ticker.replace(".KS", ".KQ"), period=period, auto_adjust=True)

        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            
            # 차트
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], 
                                         low=data['Low'], close=data['Close'], name="주가"))

            # 회귀 채널
            if show_channel:
                base, upper, lower = get_analysis(data)
                fig.add_trace(go.Scatter(x=data['Date'], y=upper, name="저항선", line=dict(color='#f87171', width=2, dash='dash')))
                fig.add_trace(go.Scatter(x=data['Date'], y=lower, name="지지선", line=dict(color='#4ade80', width=2, dash='dash')))

            # 피보나치 채널 (구역 색상 입히기)
            if show_fib:
                diff = high_v - low_v
                ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                colors = ['rgba(255,0,0,0.1)', 'rgba(255,165,0,0.1)', 'rgba(255,255,0,0.1)', 
                          'rgba(0,255,0,0.1)', 'rgba(0,0,255,0.1)', 'rgba(128,0,128,0.1)']
                for i in range(len(ratios)-1):
                    y0, y1 = high_v - (ratios[i] * diff), high_v - (ratios[i+1] * diff)
                    fig.add_hrect(y0=y0, y1=y1, fillcolor=colors[i], line_width=0)
                    fig.add_hline(y=y0, line_width=1, line_color="white", opacity=0.1)

            fig.update_layout(title=f"<b>{final_ticker}</b> 분석 결과", template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 매수/매도/손절 가이드
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
                if show_channel and curr_p <= lower[-1] * 1.02: st.success("🎯 매수 적기")
            with c2:
                if show_channel: st.metric("목표가(매도)", f"{upper[-1]:,.0f}")
            with c3:
                if show_channel: st.metric("손절가(탈출)", f"{lower[-1] * 0.97:,.0f}")
        else:
            st.error("종목을 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"오류: {e}")
