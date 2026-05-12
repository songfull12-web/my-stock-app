import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="Global Strategy Terminal", layout="wide")

# 2. 한국 주식 전종목 리스트 로드 (필터링 로직 강화)
@st.cache_data(show_spinner="전종목 데이터를 완벽하게 동기화 중...")
def get_full_krx_list():
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        # 종목코드, 종목명, 시장구분 데이터 확보
        return df[['Symbol', 'Name', 'Market']]
    except:
        # 로딩 실패 시 비상용 리스트
        return pd.DataFrame([{"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"}])

krx_full_df = get_full_krx_list()

# 3. 전략 엔진 (피보나치 6단계 + RSI + ★BUY)
def add_full_strategy(df):
    if len(df) < 20: return df
    
    # 이동평균선
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 피보나치 레벨 (0, 23.6, 38.2, 50, 61.8, 100)
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_0'], df['Fib_236'], df['Fib_382'], df['Fib_500'], df['Fib_618'], df['Fib_100'] = \
        hp, hp - 0.236 * diff, hp - 0.382 * diff, hp - 0.500 * diff, hp - 0.618 * diff, lp
    
    # ★BUY 타점 (RSI 과매도 또는 이평선 골든크로스)
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 4. 사이드바: "삼성" 입력 시 모든 종목 출력 로직
with st.sidebar:
    st.header("🔍 전종목 통합 검색")
    search_keyword = st.text_input("검색어 (예: 삼성, 에코, 카카오)", value="삼성")
    
    # [핵심 수정] 검색어가 포함된 모든 종목을 누락 없이 필터링
    kr_matches = krx_full_df[krx_full_df['Name'].str.contains(search_keyword, na=False, case=False)]
    
    if not kr_matches.empty:
        st.success(f"'{search_keyword}' 관련 종목 {len(kr_matches)}건 발견")
        
        # 종목명과 코드를 합친 리스트 생성 (사용자가 직접 고를 수 있게)
        match_list = [f"{row['Name']} ({row['Symbol']})" for _, row in kr_matches.iterrows()]
        selected_stock = st.selectbox("분석할 종목을 선택하세요", sorted(match_list))
        
        # 선택된 종목의 티커 확정
        name_part = selected_stock.split(" (")[0]
        symbol_part = selected_stock.split(" (")[1].replace(")", "")
        row = kr_matches[kr_matches['Symbol'] == symbol_part].iloc[0]
        suffix = ".KS" if row['Market'] == 'KOSPI' else ".KQ"
        final_ticker = f"{symbol_part}{suffix}"
        
        # (요청하신 기능) 코드 확인용 데이터프레임 노출
        with st.expander("검색된 전체 종목 코드 확인"):
            st.dataframe(kr_matches[['Name', 'Symbol', 'Market']], hide_index=True)
            
    else:
        st.info("해외 주식 티커 모드 (예: NVDA)")
        final_ticker = search_keyword.upper()
        name_part = search_keyword.upper()

    st.divider()
    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=0)
    show_fib = st.checkbox("피보나치 채널(강력강조)", value=True)

# 5. 메인 화면: 차트 및 매수/매도 가이드 (기존 기능 100% 유지)
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_full_strategy(data)
        
        f0, f236, f382, f500, f618, f100 = data['Fib_0'].iloc[-1], data['Fib_236'].iloc[-1], data['Fib_382'].iloc[-1], data['Fib_500'].iloc[-1], data['Fib_618'].iloc[-1], data['Fib_100'].iloc[-1]
        curr_p = float(data['Close'].iloc[-1])
        
        st.title(f"📊 {name_part} ({final_ticker}) 전략 분석")
        
        # 매수/매도 가이드 메트릭
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가", f"{curr_p:,.0f}")
        c2.metric("강력지지(61.8%)", f"{f618:,.0f}", f"{((f618/curr_p)-1)*100:.1f}%")
        c3.metric("목표가(38.2%)", f"{f382:,.0f}", f"{((f382/curr_p)-1)*100:.1f}%")
        c4.metric("손절가(LP)", f"{f100:,.0f}", f"{((f100/curr_p)-1)*100:.1f}%", delta_color="inverse")

        # 시각화
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
        
        # 캔들스틱
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        # 피보나치 채널 시각화
        if show_fib:
            levels = [(f0, f236, 'rgba(255, 0, 0, 0.1)'), (f236, f382, 'rgba(255, 165, 0, 0.1)'), (f382, f500, 'rgba(255, 255, 0, 0.05)'), (f500, f618, 'rgba(0, 255, 0, 0.1)'), (f618, f100, 'rgba(0, 0, 255, 0.1)')]
            for top, bottom, color in levels:
                fig.add_trace(go.Scatter(x=data['Date'], y=[top]*len(data), line=dict(width=0), showlegend=False, hoverinfo='skip'), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=[bottom]*len(data), fill='tonexty', fillcolor=color, line=dict(width=0.5, color='rgba(255,255,255,0.05)'), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['Date'], y=[f618]*len(data), name="GOLDEN LINE", line=dict(color='gold', width=4)), row=1, col=1)

        # ★BUY 타점
        buy_pts = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buy_pts['Date'], y=buy_pts['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buy_pts), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='타점'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='gray'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
