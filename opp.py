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
    # 분석 대상 풀 (국장 우량주 + 미장 주요주)
    target_pool = {
        "국내": {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "LG에너지솔루션": "373220.KS", "현대차": "005380.KS", "셀트리온": "068270.KS", "에코프로비엠": "247540.KQ"},
        "미국": {"NVIDIA": "NVDA", "Apple": "AAPL", "Tesla": "TSLA", "Microsoft": "MSFT", "Amazon": "AMZN", "Google": "GOOGL"}
    }
    
    recom_list = []
    
    for market, tickers in target_pool.items():
        for name, ticker in tickers.items():
            try:
                # 최근 6개월 데이터 분석
                df = yf.download(ticker, period="6mo", interval="1d", progress=False)
                if df.empty: continue
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
                # 지표 계산
                close = df['Close'].iloc[-1]
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                
                # 추천 로직 (RSI 35이하 또는 20일선 상향 돌파)
                signal = ""
                if rsi < 35: signal = "🔥 과매도 구간(저점매수)"
                elif close > ma20 and df['Close'].iloc[-2] <= ma20: signal = "🚀 골든크로스(추세전환)"
                
                if signal:
                    recom_list.append({"시장": market, "종목명": name, "티커": ticker, "RSI": round(rsi, 1), "상태": signal})
            except:
                continue
    return pd.DataFrame(recom_list)

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 엔진")
    
    # --- [추가] 실시간 추천 종목 섹션 ---
    st.subheader("🎯 실시간 매수 추천")
    if st.button("한/미 시장 스캔 시작"):
        with st.spinner("데이터 분석 중..."):
            recom_df = get_recommendations()
            if not recom_df.empty:
                st.session_state['recom_df'] = recom_df
            else:
                st.write("현재 매수 신호가 포착된 종목이 없습니다.")
    
    if 'recom_df' in st.session_state:
        st.dataframe(st.session_state['recom_df'], hide_index=True)
        st.caption("위 티커를 아래 검색창에 입력해 보세요.")
    
    st.divider()
    
    search_input = st.text_input("종목명 또는 티커 입력", value="삼성전자").strip()
    
    final_ticker = ""
    selected_name = search_input

    matches = [name for name in stock_dict.keys() if search_input in name]
    
    if matches:
        selected_name = st.selectbox(f"'{search_input}' 검색 결과", matches)
        code = stock_dict[selected_name]
        final_ticker = f"{code}.KS" if code.isdigit() else code
    else:
        final_ticker = search_input.upper()
        if len(final_ticker) == 6 and final_ticker.isdigit():
            final_ticker = f"{final_ticker}.KS"
        st.caption("💡 검색 결과가 없어 입력하신 값을 티커로 직접 사용합니다.")

    st.divider()
    interval = st.selectbox("차트 주기", ["60m", "1d", "1wk", "1mo"], index=1)
    period = st.selectbox("조회 기간", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
    
    st.subheader("🛠️ 지표 커스텀")
    show_ma = st.checkbox("이동평균선(MA)", value=True)
    show_trend = st.checkbox("추세 지지/저항선", value=True)
    show_signals = st.checkbox("매수/매도 타이밍 표시", value=True)
    show_vol = st.checkbox("거래량 차트", value=True)
    show_rsi = st.checkbox("RSI 지표", value=True)

# 4. 분석 계산 함수
def add_indicators(df):
    if len(df) < 60: return df
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    df['Buy_Signal'] = (df['RSI'] < 35) | ((df['MA20'] > df['MA60']) & (df['MA20'].shift(1) <= df['MA60'].shift(1)))
    df['Sell_Signal'] = (df['RSI'] > 65) | ((df['MA20'] < df['MA60']) & (df['MA20'].shift(1) >= df['MA60'].shift(1)))
    return df

# 5. 메인 출력 영역
if final_ticker:
    try:
        data = yf.download(final_ticker, period=period, interval=interval, auto_adjust=True)
        if (data is None or data.empty) and ".KS" in final_ticker:
            data = yf.download(final_ticker.replace(".KS", ".KQ"), period=period, interval=interval, auto_adjust=True)

        if data is not None and not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            data = add_indicators(data)
            
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            rsi_val = data['RSI'].iloc[-1] if 'RSI' in data.columns else 50

            st.title(f"📊 {selected_name} ({final_ticker})")
            m_cols = st.columns(4)
            with m_cols[0]: st.metric("현재가", f"{curr_p:,.0f}" if ".KS" in final_ticker or ".KQ" in final_ticker else f"{curr_p:,.2f}")
            with m_cols[1]: st.metric("전고점(타겟)", f"{high_v:,.0f}", f"{((high_v/curr_p)-1)*100:.1f}%")
            with m_cols[2]: st.metric("전저점(지지)", f"{low_v:,.0f}", f"{((low_v/curr_p)-1)*100:.1f}%", delta_color="normal")
            with m_cols[3]: st.metric("RSI 지수", f"{rsi_val:.1f}")

            st.divider()

            rows = 2 if show_rsi or show_vol else 1
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                               row_heights=[0.7, 0.3] if rows == 2 else [1.0],
                               specs=[[{"secondary_y": True}], [{"secondary_y": False}]] if rows == 2 else [[{"secondary_y": True}]])

            fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], 
                                       low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

            if show_signals:
                buy_pts = data[data.get('Buy_Signal', False)]
                sell_pts = data[data.get('Sell_Signal', False)]
                fig.add_trace(go.Scatter(x=buy_pts.iloc[:,0], y=buy_pts['Low']*0.98, mode='markers', 
                                         name='매수', marker=dict(symbol='triangle-up', size=12, color='#00FF00')), row=1, col=1)
                fig.add_trace(go.Scatter(x=sell_pts.iloc[:,0], y=sell_pts['High']*1.02, mode='markers', 
                                         name='매도', marker=dict(symbol='triangle-down', size=12, color='#FF0000')), row=1, col=1)

            if show_ma:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA20'], name="20일선", line=dict(color='cyan', width=1.2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA60'], name="60일선", line=dict(color='magenta', width=1.2)), row=1, col=1)

            if show_trend:
                y_v, x_v = data['Close'].values, np.arange(len(data))
                slope, _, _, _, _ = linregress(x_v, y_v)
                st.caption(f"현재 추세: {'상승' if slope > 0 else '하락'}")

            if show_vol:
                fig.add_trace(go.Bar(x=data.iloc[:,0], y=data['Volume'], name="거래량", opacity=0.4), row=rows, col=1)
            if show_rsi:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#FFD700')), row=rows, col=1)

            fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
            st.caption(f"Data Source: Yahoo Finance | Ticker: {final_ticker}")

    except Exception as e:
        st.error(f"오류 발생: {e}")
