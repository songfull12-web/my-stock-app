import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="Pro Stock Strategy Terminal", layout="wide")

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

# [부활] 실시간 매수 추천 스캐너 (손절가/목표가 포함)
def get_recommendations():
    target_pool = {
        "국내": {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS", "셀트리온": "068270.KS", "LG에너지솔루션": "373220.KS"},
        "미국": {"NVIDIA": "NVDA", "Apple": "AAPL", "Tesla": "TSLA", "Microsoft": "MSFT", "Amazon": "AMZN"}
    }
    
    recom_list = []
    for market, tickers in target_pool.items():
        for name, ticker in tickers.items():
            try:
                df = yf.download(ticker, period="6mo", interval="1d", progress=False)
                if df.empty: continue
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
                close = float(df['Close'].iloc[-1])
                # 피보나치 및 RSI 계산
                high_p, low_p = df['High'].max(), df['Low'].min()
                fib_618 = high_p - 0.618 * (high_p - low_p)
                
                delta = df['Close'].diff()
                rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
                
                # 추천 로직: 61.8% 지지선 근접 또는 RSI 과매도
                if rsi < 40 or (close <= fib_618 * 1.02):
                    recom_list.append({
                        "시장": market, "종목": name, "현재가": round(close, 2),
                        "RSI": round(rsi, 1), "상태": "🔥 매수적기" if rsi < 35 else "👀 관망/진입"
                    })
            except: continue
    return pd.DataFrame(recom_list)

# 3. 지표 계산 함수
def add_indicators(df):
    if len(df) < 20: return df
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    # 피보나치
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_0'], df['Fib_618'], df['Fib_100'] = hp, hp - 0.618 * diff, lp
    
    # 신호
    df['Buy_Signal'] = (df['Close'] > df['MA20']) & (df['Close'].shift(1) <= df['MA20'].shift(1))
    return df

# 4. 사이드바 (종목 검색 & 스캐너)
with st.sidebar:
    st.header("🎯 실시간 종목 추천")
    if st.button("전 종목 스캔 시작"):
        st.session_state['recom_df'] = get_recommendations()
    
    if 'recom_df' in st.session_state:
        st.dataframe(st.session_state['recom_df'], hide_index=True)

    st.divider()
    search_input = st.text_input("분석 종목 입력", value="삼성전자")
    matches = [n for n in stock_dict.keys() if search_input in n]
    if matches:
        selected_name = st.selectbox("검색된 종목", matches)
        code = stock_dict[selected_name]
        final_ticker = f"{code}.KS" if code.isdigit() else code
    else:
        final_ticker = search_input.upper()
        selected_name = search_input

    period = st.selectbox("기간", ["6mo", "1y", "2y"], index=0)
    show_vol = st.checkbox("거래량 보기", value=True)
    show_fib = st.checkbox("피보나치 채널", value=True)

# 5. 메인 출력 영역
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_indicators(data)
        
        curr_p = float(data['Close'].iloc[-1])
        fib_618 = data['Fib_618'].iloc[-1]
        target_p = data['Fib_0'].iloc[-1] # 전고점을 목표가로 설정
        stop_loss = data['Fib_100'].iloc[-1] # 전저점을 손절가로 설정

        # --- [신규] 매매 전략 가이드 테이블 ---
        st.title(f"🚀 {selected_name} 매매 전략")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("현재가", f"{curr_p:,.0f}")
        col2.metric("매수 타점(61.8%)", f"{fib_618:,.0f}", f"{((fib_618/curr_p)-1)*100:.1f}%")
        col3.metric("목표가(익절)", f"{target_p:,.0f}", f"{((target_p/curr_p)-1)*100:.1f}%", delta_color="normal")
        col4.metric("손절가(위험)", f"{stop_loss:,.0f}", f"{((stop_loss/curr_p)-1)*100:.1f}%", delta_color="inverse")

        st.divider()

        # 차트 구성
        rows = 2 if show_vol else 1
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3] if rows==2 else [1])

        # 캔들스틱 & 피보나치
        fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        if show_fib:
            levels = [('Fib_0', '0% (목표)'), ('Fib_618', '61.8% (지지)'), ('Fib_100', '100% (손절)')]
            for col, name in levels:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data[col], name=name, line=dict(dash='dash', width=1)), row=1, col=1)

        # 매수 신호 마커
        buy_pts = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buy_pts.iloc[:,0], y=buy_pts['Low']*0.97, mode='markers+text', text=["BUY"], textposition="bottom center", marker=dict(symbol='triangle-up', size=12, color='lime'), name='매수신호'), row=1, col=1)

        # 거래량
        if show_vol:
            colors = ['red' if r['Open'] < r['Close'] else 'blue' for _, r in data.iterrows()]
            fig.add_trace(go.Bar(x=data.iloc[:,0], y=data['Volume'], marker_color=colors, name="거래량"), row=2, col=1)

        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
