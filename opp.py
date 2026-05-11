import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Professional Stock Terminal", layout="wide")

# 2. 종목 데이터 로드
@st.cache_data
def get_stock_dict():
    stocks = {"삼성전자": "005930", "SK하이닉스": "000660", "현대차": "005380", "NAVER": "035420", "카카오": "035720"}
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        for _, row in df.iterrows():
            stocks[str(row['Name'])] = str(row['Symbol']).zfill(6)
    except:
        pass
    return stocks

stock_dict = get_stock_dict()

# [신규] 실시간 매수 추천 스캐너 함수
def get_recommendations():
    target_pool = {
        "국내": {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "LG에너지솔루션": "373220.KS", "현대차": "005380.KS", "셀트리온": "068270.KS"},
        "미국": {"NVIDIA": "NVDA", "Apple": "AAPL", "Tesla": "TSLA", "Microsoft": "MSFT", "Amazon": "AMZN"}
    }
    
    recom_list = []
    for market, tickers in target_pool.items():
        for name, ticker in tickers.items():
            try:
                df = yf.download(ticker, period="6mo", interval="1d", progress=False)
                if df.empty: continue
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
                close = df['Close'].iloc[-1]
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                
                # 피보나치 계산
                high_p, low_p = df['High'].max(), df['Low'].min()
                fib_618 = high_p - 0.618 * (high_p - low_p)
                
                signal = ""
                # 타점 선행 알림 (미리 알려주는 기능)
                if 35 <= rsi <= 40 or (close <= fib_618 * 1.02 and close > fib_618):
                    signal = "⚠️ 매수 대기 (지지선 접근)"
                elif rsi < 35: 
                    signal = "🔥 과매도 (강력 매수)"
                elif close > ma20 and df['Close'].iloc[-2] <= ma20: 
                    signal = "🚀 골든크로스"
                
                if signal:
                    recom_list.append({"시장": market, "종목명": name, "RSI": round(rsi, 1), "상태": signal})
            except: continue
    return pd.DataFrame(recom_list)

# 3. 분석 계산 함수 (피보나치 및 매수 타점 로직)
def add_indicators(df):
    if len(df) < 20: return df
    
    # 이평선 및 RSI
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 피보나치 채널 계산 (조회 기간 기준)
    high_p, low_p = df['High'].max(), df['Low'].min()
    diff = high_p - low_p
    df['Fib_0'] = high_p
    df['Fib_236'] = high_p - 0.236 * diff
    df['Fib_382'] = high_p - 0.382 * diff
    df['Fib_500'] = high_p - 0.5 * diff
    df['Fib_618'] = high_p - 0.618 * diff
    df['Fib_100'] = low_price = low_p
    
    # 매수/매도 신호 로직
    df['Buy_Signal'] = (df['RSI'] < 35) | ((df['MA20'] > df['MA60']) & (df['MA20'].shift(1) <= df['MA60'].shift(1)))
    df['Sell_Signal'] = (df['RSI'] > 65) | ((df['MA20'] < df['MA60']) & (df['MA20'].shift(1) >= df['MA60'].shift(1)))
    
    return df

# 4. 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 엔진")
    st.subheader("🎯 실시간 스캐너")
    if st.button("시장 스캔 시작"):
        with st.spinner("분석 중..."):
            recom_df = get_recommendations()
            st.session_state['recom_df'] = recom_df
    
    if 'recom_df' in st.session_state:
        st.dataframe(st.session_state['recom_df'], hide_index=True)
    
    st.divider()
    search_input = st.text_input("종목명/티커 입력", value="삼성전자").strip()
    matches = [name for name in stock_dict.keys() if search_input in name]
    
    if matches:
        selected_name = st.selectbox(f"검색 결과", matches)
        code = stock_dict[selected_name]
        final_ticker = f"{code}.KS" if code.isdigit() else code
    else:
        final_ticker = search_input.upper()
        selected_name = search_input

    interval = st.selectbox("차트 주기", ["60m", "1d", "1wk"], index=1)
    period = st.selectbox("조회 기간", ["3mo", "6mo", "1y", "2y"], index=1)
    
    st.subheader("🛠️ 시각화 옵션")
    show_fib = st.checkbox("피보나치 채널 활성화", value=True)
    show_ma = st.checkbox("이동평균선", value=True)
    show_rsi = st.checkbox("RSI 보조지표", value=True)

# 5. 메인 출력 영역
if final_ticker:
    try:
        data = yf.download(final_ticker, period=period, interval=interval, auto_adjust=True)
        if data.empty: st.error("데이터를 불러올 수 없습니다.")
        else:
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            data = add_indicators(data)
            
            curr_p = float(data['Close'].iloc[-1])
            rsi_val = data['RSI'].iloc[-1]
            fib_618_val = data['Fib_618'].iloc[-1]

            # 상단 메트릭 및 알림
            st.title(f"📊 {selected_name} ({final_ticker})")
            
            # 매수 타점 선행 알림 표시
            if curr_p <= fib_618_val * 1.01 and curr_p >= fib_618_val:
                st.warning(f"🔔 **매수 타점 임박:** 주가가 피보나치 61.8% 지지선({fib_618_val:,.0f})에 근접했습니다!")
            elif rsi_val < 35:
                st.error(f"🔥 **강력 매수 신호:** RSI({rsi_val:.1f}) 과매도 구간입니다.")

            m_cols = st.columns(4)
            m_cols[0].metric("현재가", f"{curr_p:,.0f}")
            m_cols[1].metric("RSI", f"{rsi_val:.1f}")
            m_cols[2].metric("61.8% 지지선", f"{fib_618_val:,.0f}")
            m_cols[3].metric("전고점", f"{data['Fib_0'].iloc[-1]:,.0f}")

            # 차트 생성
            rows = 2 if show_rsi else 1
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3] if rows==2 else [1.0])

            # 캔들스틱
            fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="Price"), row=1, col=1)

            # 피보나치 채널 시각화 (영역 채우기 추가)
            if show_fib:
                colors = ['rgba(255, 0, 0, 0.1)', 'rgba(255, 165, 0, 0.1)', 'rgba(0, 255, 0, 0.1)', 'rgba(0, 0, 255, 0.1)']
                levels = [('Fib_0', 'Fib_236', '0%~23.6%'), ('Fib_236', 'Fib_382', '23.6%~38.2%'), 
                          ('Fib_382', 'Fib_500', '38.2%~50%'), ('Fib_500', 'Fib_618', '50%~61.8%')]
                
                for i, (start, end, label) in enumerate(levels):
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data[start], line=dict(width=0), showlegend=False), row=1, col=1)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data[end], fill='tonexty', fillcolor=colors[i], line=dict(width=0.5, color='gray', dash='dot'), name=label), row=1, col=1)
                
                # 주요 지지선 강조 (61.8%)
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['Fib_618'], name="Golden Support(61.8%)", line=dict(color='gold', width=3)), row=1, col=1)

            # 매수/매도 마커
            buy_pts = data[data['Buy_Signal']]
            fig.add_trace(go.Scatter(x=buy_pts.iloc[:,0], y=buy_pts['Low']*0.97, mode='markers', name='BUY', marker=dict(symbol='triangle-up', size=15, color='#00FF00')), row=1, col=1)

            if show_ma:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA20'], name="20 MA", line=dict(color='cyan', width=1.5)), row=1, col=1)

            if show_rsi:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#FFD700')), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

            fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"분석 중 오류가 발생했습니다: {e}")
