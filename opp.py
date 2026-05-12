import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="High-Visibility Strategy Terminal", layout="wide")

# 2. 한국 주식 전종목 리스트 로드 (안정성 극대화)
@st.cache_data(show_spinner="전체 종목 데이터를 동기화 중입니다...")
def get_all_korean_stocks():
    try:
        # 실시간 KRX 종목 데이터 소스
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        
        # 이름: 티커(.KS/.KQ) 맵핑
        stock_map = {
            str(row['Name']): f"{str(row['Symbol']).zfill(6)}{'.KS' if row['Market'] == 'KOSPI' else '.KQ'}"
            for _, row in df.iterrows()
        }
        return stock_map
    except:
        # 로드 실패 시 핵심 우량주 리스트
        return {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "셀트리온": "068270.KS", "현대차": "005380.KS"}

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

# 3. 보조지표 계산 (기존 피보나치/매수신호/★BUY 로직)
def add_indicators(df):
    if len(df) < 20: return df
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

# 4. 사이드바 - 검색 및 티커 리스트 출력 기능 (요청하신 부분)
with st.sidebar:
    st.header("🎯 실시간 스캐너")
    if st.button("시장 스캔 시작"):
        st.session_state['recom_df'] = get_recommendations()
    if 'recom_df' in st.session_state:
        st.dataframe(st.session_state['recom_df'], hide_index=True)

    st.divider()
    st.header("🔍 전종목 검색 엔진")
    search_term = st.text_input("종목명 입력 (예: 삼성, 에코, 카카오)", value="삼성전자")
    
    # [검색 필터링 및 리스트 생성]
    search_results = [n for n in stock_dict.keys() if search_term.upper() in n.upper()]
    
    if search_results:
        # 1. 드롭다운 선택박스
        selected_name = st.selectbox(f"검색된 종목 ({len(search_results)}건)", sorted(search_results))
        final_ticker = stock_dict[selected_name]
        
        # 2. 직접 복사용 티커 리스트 (요청하신 기능)
        st.info("💡 아래 리스트에서 코드를 확인/복사 하세요:")
        ticker_list_df = pd.DataFrame([
            {"종목명": name, "티커코드": stock_dict[name]} 
            for name in sorted(search_results)
        ])
        st.dataframe(ticker_list_df, hide_index=True, height=200) # 표 형태로 코드 나열
    else:
        st.warning("한국 주식 검색 결과가 없습니다.")
        final_ticker = search_term.upper()
        selected_name = search_term

    period = st.selectbox("조회 기간", ["6mo", "1y", "2y"], index=0)
    
    st.subheader("🛠️ 지표 설정")
    show_ma = st.checkbox("이동평균선 표시", value=True)
    show_fib = st.checkbox("피보나치(강력강조)", value=True)
    show_vol = st.checkbox("거래량 표시", value=True)

# 5. 메인 영역 (분석 기능 완벽 유지)
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_indicators(data)
        
        if 'Fib_0' in data.columns:
            curr_p = float(data['Close'].iloc[-1])
            f0, f236, f382, f500, f618, f100 = data['Fib_0'].iloc[-1], data['Fib_236'].iloc[-1], data['Fib_382'].iloc[-1], data['Fib_500'].iloc[-1], data['Fib_618'].iloc[-1], data['Fib_100'].iloc[-1]

            st.title(f"📊 {selected_name} ({final_ticker}) 분석 리포트")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("현재가", f"{curr_p:,.0f}")
            col2.metric("황금지지(61.8%)", f"{f618:,.0f}", f"{((f618/curr_p)-1)*100:.1f}%")
            col3.metric("1차목표(38.2%)", f"{f382:,.0f}", f"{((f382/curr_p)-1)*100:.1f}%")
            col4.metric("손절라인", f"{f100:,.0f}", f"{((f100/curr_p)-1)*100:.1f}%", delta_color="inverse")

            rows = 2 if show_vol else 1
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25] if rows==2 else [1])

            # 피보나치 채널 색상 강조
            if show_fib:
                levels = [(f0, f236, 'rgba(255, 0, 0, 0.15)'), (f236, f382, 'rgba(255, 165, 0, 0.1)'), (f382, f500, 'rgba(255, 255, 0, 0.08)'), (f500, f618, 'rgba(0, 255, 0, 0.1)'), (f618, f100, 'rgba(0, 0, 255, 0.15)')]
                for top, bottom, color in levels:
                    fig.add_trace(go.Scatter(x=data['Date'], y=[top]*len(data), line=dict(width=0), showlegend=False, hoverinfo='skip'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=data['Date'], y=[bottom]*len(data), fill='tonexty', fillcolor=color, line=dict(width=0.5, color='rgba(255,255,255,0.1)'), showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=[f618]*len(data), name="GOLDEN LINE", line=dict(color='gold', width=4)), row=1, col=1)

            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

            if show_ma:
                for col, color in [('MA5', 'orange'), ('MA20', 'cyan'), ('MA60', 'magenta'), ('MA120', 'white')]:
                    if col in data.columns: fig.add_trace(go.Scatter(x=data['Date'], y=data[col], name=col, line=dict(color=color, width=1.5)), row=1, col=1)

            # 매수 타점 (★BUY) 복구
            if 'Buy_Signal' in data.columns:
                buy_pts = data[data['Buy_Signal']]
                fig.add_trace(go.Scatter(x=buy_pts['Date'], y=buy_pts['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buy_pts), textposition="bottom center", marker=dict(symbol='star', size=12, color='yellow'), name='타점'), row=1, col=1)

            if show_vol:
                v_colors = ['red' if r['Open'] < r['Close'] else 'blue' for _, r in data.iterrows()]
                fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], marker_color=v_colors, name="거래량"), row=2, col=1)

            fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
