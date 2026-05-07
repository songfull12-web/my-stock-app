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

# [신규] 3. 매수 추천 종목 스캐너 함수 (한/미 주요 종목)
def scan_buy_opportunities():
    # 분석 대상 (한/미 핵심 우량주)
    targets = {
        "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS", 
        "Apple": "AAPL", "NVIDIA": "NVDA", "Tesla": "TSLA", "Microsoft": "MSFT", "Amazon": "AMZN"
    }
    results = []
    for name, ticker in targets.items():
        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            # 지표 계산
            close = float(df['Close'].iloc[-1])
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            
            # 매수 조건 판단
            reason = ""
            if rsi < 35: reason = "🔥 과매도(저평가)"
            elif close > ma20 and df['Close'].iloc[-2] <= ma20: reason = "🚀 상승 추세 전환"
            elif close < df['Low'].min() * 1.05: reason = "💎 바닥권 근접"
            
            if reason:
                results.append({"종목": name, "티커": ticker, "현재가": f"{close:,.2f}", "RSI": f"{rsi:.1f}", "추천 이유": reason})
        except: continue
    return pd.DataFrame(results)

# 4. 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 엔진")
    search_input = st.text_input("종목명 검색 (예: 삼성)", value="삼성").strip()
    matches = [name for name in stock_dict.keys() if search_input in name]
    
    final_ticker, selected_name = "", ""
    if matches:
        selected_name = st.selectbox(f"'{search_input}' 검색 결과", matches)
        final_ticker = f"{stock_dict[selected_name]}.KS"
    else:
        final_ticker = search_input.upper()
        if len(final_ticker) == 6 and final_ticker.isdigit(): final_ticker += ".KS"
        selected_name = search_input

    st.divider()
    # [추가] 매수 추천 버튼
    if st.button("🎯 실시간 매수 추천 종목 스캔"):
        with st.spinner("한/미 시장 분석 중..."):
            recom_df = scan_buy_opportunities()
            st.session_state['recoms'] = recom_df

    if 'recoms' in st.session_state:
        st.subheader("✅ AI 추천 리스트")
        st.dataframe(st.session_state['recoms'], hide_index=True)

    st.divider()
    interval = st.selectbox("차트 주기", ["60m", "1d", "1wk", "1mo"], index=1)
    period = st.selectbox("조회 기간", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
    
    st.subheader("🛠️ 지표 커스텀")
    show_ma = st.checkbox("이동평균선", value=True)
    show_trend = st.checkbox("추세선", value=True)
    show_signals = st.checkbox("매수/매도 신호", value=True)
    show_rsi = st.checkbox("RSI", value=True)

# 5. 분석 함수 및 메인 로직 (기존 유지)
def add_indicators(df):
    if len(df) < 60: return df
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['Buy_Signal'] = (df['RSI'] < 35) | ((df['MA20'] > df['MA60']) & (df['MA20'].shift(1) <= df['MA60'].shift(1)))
    df['Sell_Signal'] = (df['RSI'] > 65) | ((df['MA20'] < df['MA60']) & (df['MA20'].shift(1) >= df['MA60'].shift(1)))
    return df

if final_ticker:
    try:
        data = yf.download(final_ticker, period=period, interval=interval, auto_adjust=True)
        if (data is None or data.empty) and ".KS" in final_ticker:
            data = yf.download(final_ticker.replace(".KS", ".KQ"), period=period, interval=interval, auto_adjust=True)

        if data is not None and not data.empty:
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            data = data.reset_index(); data = add_indicators(data)
            
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            
            st.title(f"📊 {selected_name} ({final_ticker})")
            m_cols = st.columns(4)
            m_cols[0].metric("현재가", f"{curr_p:,.2f}")
            m_cols[1].metric("전고점(타겟)", f"{high_v:,.2f}", f"{((high_v/curr_p)-1)*100:.1f}%")
            m_cols[2].metric("전저점(지지)", f"{low_v:,.2f}", f"{((low_v/curr_p)-1)*100:.1f}%", delta_color="normal")
            m_cols[3].metric("RSI", f"{data['RSI'].iloc[-1]:.1f}")

            # 차트 그리기 (기존 동일)
            fig = make_subplots(rows=2 if show_rsi else 1, cols=1, shared_xaxes=True, vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
            
            if show_signals:
                b = data[data.get('Buy_Signal', False)]; s = data[data.get('Sell_Signal', False)]
                fig.add_trace(go.Scatter(x=b.iloc[:,0], y=b['Low']*0.98, mode='markers', name='매수', marker=dict(symbol='triangle-up', size=12, color='#00FF00')), row=1, col=1)
                fig.add_trace(go.Scatter(x=s.iloc[:,0], y=s['High']*1.02, mode='markers', name='매도', marker=dict(symbol='triangle-down', size=12, color='#FF0000')), row=1, col=1)

            if show_rsi:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#FFD700')), row=2, col=1)

            fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e: st.error(f"오류: {e}")
