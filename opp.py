import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="Ultimate Stock Terminal", layout="wide")

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

# [추천 엔진] RSI + 피보나치 기반 스캐너
def get_recommendations():
    target_pool = {
        "국내": {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS", "셀트리온": "068270.KS", "LG화학": "051910.KS"},
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
                hp, lp = df['High'].max(), df['Low'].min()
                fib_618 = hp - 0.618 * (hp - lp)
                
                delta = df['Close'].diff()
                rsi = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean()))).iloc[-1]
                
                if rsi < 40 or (close <= fib_618 * 1.02):
                    recom_list.append({"시장": market, "종목": name, "가격": round(close, 2), "상태": "🔥 매수기회" if rsi < 35 else "👀 대기"})
            except: continue
    return pd.DataFrame(recom_list)

# 3. 보조지표 계산 (이동평균선 5, 20, 60, 120일 포함)
def add_indicators(df):
    if len(df) < 120: return df
    # 이동평균선
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA120'] = df['Close'].rolling(window=120).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 피보나치
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_0'], df['Fib_236'], df['Fib_382'], df['Fib_500'], df['Fib_618'], df['Fib_100'] = \
        hp, hp-0.236*diff, hp-0.382*diff, hp-0.5*diff, hp-0.618*diff, lp
    
    # 타점 (골든크로스 or 과매도)
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    df['Sell_Signal'] = (df['RSI'] > 70)
    return df

# 4. 사이드바
with st.sidebar:
    st.header("🎯 실시간 스캐너")
    if st.button("시장 종목 스캔"):
        st.session_state['recom_df'] = get_recommendations()
    if 'recom_df' in st.session_state:
        st.dataframe(st.session_state['recom_df'], hide_index=True)

    st.divider()
    search_input = st.text_input("종목명 입력", value="삼성전자")
    matches = [n for n in stock_dict.keys() if search_input in n]
    if matches:
        selected_name = st.selectbox("검색 결과", matches)
        code = stock_dict[selected_name]
        final_ticker = f"{code}.KS" if code.isdigit() else code
    else:
        final_ticker = search_input.upper()
        selected_name = search_input

    period = st.selectbox("조회 기간", ["6mo", "1y", "2y", "5y"], index=1)
    
    st.subheader("🛠️ 지표 On/Off")
    show_ma = st.checkbox("이동평균선 (5,20,60,120)", value=True)
    show_fib = st.checkbox("피보나치 채널 영역", value=True)
    show_vol = st.checkbox("거래량", value=True)
    show_rsi = st.checkbox("RSI", value=True)

# 5. 메인 출력 영역
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_indicators(data)
        
        curr_p = float(data['Close'].iloc[-1])
        f618, f0, f100 = data['Fib_618'].iloc[-1], data['Fib_0'].iloc[-1], data['Fib_100'].iloc[-1]

        # 상단 전략 대시보드
        st.title(f"📈 {selected_name} 매매 가이드라인")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가", f"{curr_p:,.0f}")
        c2.metric("매수타점(61.8%)", f"{f618:,.0f}", f"{((f618/curr_p)-1)*100:.1f}%")
        c3.metric("익절가(전고점)", f"{f0:,.0f}", f"{((f0/curr_p)-1)*100:.1f}%", delta_color="normal")
        c4.metric("손절가(전저점)", f"{f100:,.0f}", f"{((f100/curr_p)-1)*100:.1f}%", delta_color="inverse")

        # 차트 레이아웃
        rows = 3 if (show_vol and show_rsi) else (2 if (show_vol or show_rsi) else 1)
        row_h = [0.6] + [0.2] * (rows-1)
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=row_h)

        # 1. 캔들스틱
        fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

        # 2. 이동평균선 (부활!)
        if show_ma:
            ma_list = [('MA5', 'orange', 1), ('MA20', 'cyan', 1.5), ('MA60', 'magenta', 1.5), ('MA120', 'white', 2)]
            for col, color, width in ma_list:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data[col], name=col, line=dict(color=color, width=width)), row=1, col=1)

        # 3. 피보나치 영역
        if show_fib:
            fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['Fib_618'], name="61.8% 지지", line=dict(color='gold', width=2, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['Fib_0'], name="0% 저항", line=dict(color='red', width=1, dash='dot')), row=1, col=1)

        # 4. 매수 신호 마커
        buy_pts = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buy_pts.iloc[:,0], y=buy_pts['Low']*0.95, mode='markers+text', text=["BUY"], textposition="bottom center", marker=dict(symbol='triangle-up', size=15, color='lime'), name='매수타점'), row=1, col=1)

        # 5. 거래량
        if show_vol:
            v_row = 2
            colors = ['red' if r['Open'] < r['Close'] else 'blue' for _, r in data.iterrows()]
            fig.add_trace(go.Bar(x=data.iloc[:,0], y=data['Volume'], marker_color=colors, name="거래량"), row=v_row, col=1)

        # 6. RSI
        if show_rsi:
            r_row = rows
            fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='yellow')), row=r_row, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=r_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=r_row, col=1)

        fig.update_layout(template="plotly_dark", height=900, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
