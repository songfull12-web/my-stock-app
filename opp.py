import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="Global Strategy Terminal", layout="wide")

# 2. 한국 주식 전종목 리스트 로드 (안정성 강화)
@st.cache_data(show_spinner="전종목 데이터를 불러오는 중...")
def get_krx_list():
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Symbol', 'Name', 'Market']]
    except:
        return pd.DataFrame([{"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"}])

krx_df = get_krx_list()

# 3. 기존 [해외/국내] 추천 스캐너 로직 (그대로 유지)
def get_recommendations():
    target_pool = {
        "국내": {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS"},
        "미국": {"NVIDIA": "NVDA", "Apple": "AAPL", "Tesla": "TSLA", "Microsoft": "MSFT", "Google": "GOOGL"}
    }
    recom_list = []
    for market, tickers in target_pool.items():
        for name, ticker in tickers.items():
            try:
                df = yf.download(ticker, period="6mo", interval="1d", progress=False)
                if df.empty: continue
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                close = float(df['Close'].iloc[-1])
                hp, lp = df['High'].max(), df['Low'].min()
                fib_618 = hp - 0.618 * (hp - lp)
                delta = df['Close'].diff()
                rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
                if rsi < 45 or (close <= fib_618 * 1.05):
                    recom_list.append({"시장": market, "종목": name, "가격": round(close, 2), "상태": "🔥 기회"})
            except: continue
    return pd.DataFrame(recom_list)

# 4. 사이드바 구성 (기존 기능 + 신규 검색 기능)
with st.sidebar:
    # (기존) 추천 스캐너
    st.header("🎯 실시간 스캐너")
    if st.button("전세계 시장 스캔"):
        st.session_state['recom_df'] = get_recommendations()
    if 'recom_df' in st.session_state:
        st.dataframe(st.session_state['recom_df'], hide_index=True)

    st.divider()

    # (신규) 한국주식 코드 찾기 칸
    st.header("🔍 한국주식 코드 찾기")
    search_keyword = st.text_input("종목명 입력 (예: 삼성, 에코)", value="삼성")
    filtered_df = krx_df[krx_df['Name'].str.contains(search_keyword, na=False)]
    if not filtered_df.empty:
        st.dataframe(filtered_df[['Name', 'Symbol', 'Market']], hide_index=True, height=150)
    
    st.divider()

    # (기존/강화) 통합 분석 입력창
    st.header("📊 분석 대상 입력")
    market_select = st.radio("시장 선택", ["미국 (티커)", "코스피 (KS)", "코스닥 (KQ)"], horizontal=True)
    user_input = st.text_input("티커 또는 코드 입력 (예: NVDA, 005930)", value="NVDA")
    
    if market_select == "미국 (티커)":
        final_ticker = user_input.upper()
    elif market_select == "코스피 (KS)":
        final_ticker = f"{user_input.strip()}.KS"
    else:
        final_ticker = f"{user_input.strip()}.KQ"

    period = st.selectbox("기간", ["6mo", "1y", "2y"])

# 5. 메인 차트 엔진 (피보나치, ★BUY 타점 그대로 유지)
def add_indicators(df):
    if len(df) < 20: return df
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_618'] = hp - 0.618 * diff
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_indicators(data)
        
        st.title(f"📈 {final_ticker} 분석 리포트")
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        if 'Fib_618' in data.columns:
            f618 = data['Fib_618'].iloc[-1]
            fig.add_trace(go.Scatter(x=data['Date'], y=[f618]*len(data), name="GOLDEN LINE", line=dict(color='gold', width=3, dash='dash')), row=1, col=1)
        
        buy_pts = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buy_pts['Date'], y=buy_pts['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buy_pts), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='타점'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='gray'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
