import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="High-Visibility Strategy Terminal", layout="wide")

# 2. 한국 주식 전종목(KOSPI/KOSDAQ/KONEX) 리스트 및 마켓 매핑 로드
@st.cache_data
def get_all_korean_stocks():
    # 기본 폴백 데이터
    stocks = {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS", "셀트리온": "068270.KS"}
    try:
        # 한국거래소(KRX) 전체 상장 종목 리스트 (가장 최신 소스)
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        
        # 전체 종목 맵 생성
        all_stocks = {}
        for _, row in df.iterrows():
            name = str(row['Name'])
            code = str(row['Symbol']).zfill(6)
            market = str(row['Market'])
            # yfinance 호환용 접미사 (KOSPI는 .KS, 그 외 코스닥/코넥스는 .KQ)
            suffix = ".KS" if market == 'KOSPI' else ".KQ"
            all_stocks[name] = f"{code}{suffix}"
        return all_stocks
    except:
        return stocks

stock_dict = get_all_korean_stocks()

# [기존 추천 엔진 유지]
def get_recommendations():
    target_pool = {
        "국내": {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS", "셀트리온": "068270.KS"},
        "미국": {"NVIDIA": "NVDA", "Apple": "AAPL", "Tesla": "TSLA", "Microsoft": "MSFT"}
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
                    recom_list.append({"시장": market, "종목": name, "가격": round(close, 2), "상태": "🔥 매수기회"})
            except: continue
    return pd.DataFrame(recom_list)

# 3. 보조지표 및 피보나치 계산 (기존 로직 유지)
def add_indicators(df):
    if len(df) < 10: return df # 데이터 부족 시 에러 방지용 최소치 하향
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    df['MA120'] = df['Close'].rolling(120).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_0'], df['Fib_236'], df['Fib_382'], df['Fib_500'], df['Fib_618'], df['Fib_100'] = \
        hp, hp - 0.236 * diff, hp - 0.382 * diff, hp - 0.5 * diff, hp - 0.618 * diff, lp
    
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 4. 사이드바 - 검색 로직 업그레이드 (핵심 요청 사항)
with st.sidebar:
    st.header("🎯 실시간 스캐너")
    if st.button("시장 스캔 시작"):
        st.session_state['recom_df'] = get_recommendations()
    if 'recom_df' in st.session_state:
        st.dataframe(st.session_state['recom_df'], hide_index=True)

    st.divider()
    st.header("🔍 종목 검색")
    search_input = st.text_input("종목명 입력 (예: 삼성, 셀트리온, 에코)", value="삼성전자")
    
    # [업그레이드된 검색 로직]: "삼성" 입력 시 "삼성전자", "삼성SDI" 등이 모두 포함된 리스트 반환
    matches = [name for name in stock_dict.keys() if search_input.upper() in name.upper()]
    
    if matches:
        # 검색된 리스트 중 하나를 선택할 수 있게 함
        selected_name = st.selectbox(f"검색 결과 ({len(matches)}건)", sorted(matches))
        final_ticker = stock_dict[selected_name]
    else:
        # 검색 결과 없으면 직접 입력 티커(예: NVDA)로 사용
        final_ticker = search_input.upper()
        selected_name = search_input

    period = st.selectbox("조회 기간", ["6mo", "1y", "2y"], index=0)
    
    st.subheader("🛠️ 지표 설정")
    show_ma = st.checkbox("이동평균선 표시", value=True)
    show_fib = st.checkbox("피보나치(강력강조)", value=True)
    show_vol = st.checkbox("거래량 표시", value=True)

# 5. 메인 영역 (기존 시각화 로직 완벽 유지)
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_indicators(data)
        
        if 'Fib_0' in data.columns:
            curr_p = float(data['Close'].iloc[-1])
            f0, f236, f382, f500, f618, f100 = data['Fib_0'].iloc[-1], data['Fib_236'].iloc[-1], data['Fib_382'].iloc[-1], data['Fib_500'].iloc[-1], data['Fib_618'].iloc[-1], data['Fib_100'].iloc[-1]

            st.title(f"📊 {selected_name} 매매 전략 가이드")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("현재가", f"{curr_p:,.0f}")
            col2.metric("황금지지(61.8%)", f"{f618:,.0f}", f"{((f618/curr_p)-1)*100:.1f}%")
            col3.metric("1차목표(38.2%)", f"{f382:,.0f}", f"{((f382/curr_p)-1)*100:.1f}%")
            col4.metric("손절라인(전저점)", f"{f100:,.0f}", f"{((f100/curr_p)-1)*100:.1f}%", delta_color="inverse")

            rows = 2 if show_vol else 1
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25] if rows==2 else [1])

            if show_fib:
                levels = [(f0, f236, 'rgba(255, 0, 0, 0.15)'), (f236, f382, 'rgba(255, 165, 0, 0.1)'), (f382, f500, 'rgba(255, 255, 0, 0.08)'), (f500, f618, 'rgba(0, 255, 0, 0.1)'), (f618, f100, 'rgba(0, 0, 255, 0.15)')]
                for top, bottom, color in levels:
                    fig.add_trace(go.Scatter(x=data['Date'], y=[top]*len(data), line=dict(width=0), showlegend=False, hoverinfo='skip'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=data['Date'], y=[bottom]*len(data), fill='tonexty', fillcolor=color, line=dict(width=1, color='rgba(255,255,255,0.1)'), showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=[f618]*len(data), name="GOLDEN LINE", line=dict(color='gold', width=4)), row=1, col=1)

            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

            if show_ma:
                for col, color in [('MA5', 'orange'), ('MA20', 'cyan'), ('MA60', 'magenta'), ('MA120', 'white')]:
                    if col in data.columns: fig.add_trace(go.Scatter(x=data['Date'], y=data[col], name=col, line=dict(color=color, width=1.5)), row=1, col=1)

            if 'Buy_Signal' in data.columns:
                buy_pts = data[data['Buy_Signal']]
                fig.add_trace(go.Scatter(x=buy_pts['Date'], y=buy_pts['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buy_pts), textposition="bottom center", marker=dict(symbol='star', size=12, color='yellow'), name='타점'), row=1, col=1)

            if show_vol:
                v_colors = ['red' if r['Open'] < r['Close'] else 'blue' for _, r in data.iterrows()]
                fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], marker_color=v_colors, name="거래량"), row=2, col=1)

            fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
