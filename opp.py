import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="Global Multi-Strategy Terminal", layout="wide")

# 2. 한국 주식 전종목 리스트 로드 (정확도 우선)
@st.cache_data(show_spinner="전종목 데이터를 동기화 중...")
def get_full_krx_list():
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Symbol', 'Name', 'Market']]
    except:
        return pd.DataFrame([{"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"}])

krx_full_df = get_full_krx_list()

# 3. 보조지표 및 피보나치/타점 엔진 (기존 기능 100% 복구)
def add_full_strategy(df):
    if len(df) < 20: return df
    
    # 이동평균선
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    df['MA120'] = df['Close'].rolling(120).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 피보나치 모든 레벨 (HP/LP 기준)
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_0'] = hp
    df['Fib_236'] = hp - 0.236 * diff
    df['Fib_382'] = hp - 0.382 * diff
    df['Fib_500'] = hp - 0.500 * diff
    df['Fib_618'] = hp - 0.618 * diff
    df['Fib_100'] = lp
    
    # ★BUY 타점 로직 (골든크로스 or 과매도)
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 4. 사이드바 구성 (검색 기능 강화 + 기존 옵션)
with st.sidebar:
    st.header("🔍 전종목 통합 검색")
    search_input = st.text_input("검색어 (종목명 또는 티커)", value="삼성")
    
    # 한국 주식 필터링
    kr_matches = krx_full_df[krx_full_df['Name'].str.contains(search_input, na=False, case=False)]
    
    if not kr_matches.empty:
        st.success(f"국내주식 검색 결과: {len(kr_matches)}건")
        kr_matches['Display'] = kr_matches['Name'] + " (" + kr_matches['Symbol'] + ")"
        selected_display = st.selectbox("분석할 국내 종목 선택", kr_matches['Display'].tolist())
        
        row = kr_matches[kr_matches['Display'] == selected_display].iloc[0]
        selected_name = row['Name']
        suffix = ".KS" if row['Market'] == 'KOSPI' else ".KQ"
        final_ticker = f"{row['Symbol']}{suffix}"
        
        # 코드 확인용 표 (요청하신 기능)
        with st.expander("검색 리스트 및 코드 확인"):
            st.dataframe(kr_matches[['Name', 'Symbol', 'Market']], hide_index=True)
    else:
        st.info("해외 티커 모드")
        final_ticker = search_input.upper()
        selected_name = search_input.upper()

    st.divider()
    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=0)
    
    st.subheader("🛠️ 지표 설정")
    show_ma = st.checkbox("이동평균선", value=True)
    show_fib = st.checkbox("피보나치 채널(강력강조)", value=True)
    show_vol = st.checkbox("거래량", value=True)

# 5. 메인 화면 (차트 + 매수/매도 가격 가이드)
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_full_strategy(data)
        
        # [기존 기능] 매수/매도 타점 및 목표가 가이드 영역
        f0, f236, f382, f500, f618, f100 = data['Fib_0'].iloc[-1], data['Fib_236'].iloc[-1], data['Fib_382'].iloc[-1], data['Fib_500'].iloc[-1], data['Fib_618'].iloc[-1], data['Fib_100'].iloc[-1]
        curr_p = float(data['Close'].iloc[-1])
        
        st.title(f"📊 {selected_name} ({final_ticker}) 전략 리포트")
        
        # 상단 메트릭 (매수/매도 가이드)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가", f"{curr_p:,.0f}")
        c2.metric("강력매수(61.8%)", f"{f618:,.0f}", f"{((f618/curr_p)-1)*100:.1f}%")
        c3.metric("매도목표(38.2%)", f"{f382:,.0f}", f"{((f382/curr_p)-1)*100:.1f}%")
        c4.metric("손절라인(LP)", f"{f100:,.0f}", f"{((f100/curr_p)-1)*100:.1f}%", delta_color="inverse")

        # 차트 시각화
        fig = make_subplots(rows=2 if show_vol else 1, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25] if show_vol else [1])
        
        # 피보나치 채널 (강력 강조 시각화 복구)
        if show_fib:
            levels = [
                (f0, f236, 'rgba(255, 0, 0, 0.15)', 'Overbought'),
                (f236, f382, 'rgba(255, 165, 0, 0.1)', 'Take Profit'),
                (f382, f500, 'rgba(255, 255, 0, 0.08)', 'Neutral'),
                (f500, f618, 'rgba(0, 255, 0, 0.1)', 'Buy Zone'),
                (f618, f100, 'rgba(0, 0, 255, 0.15)', 'Deep Support')
            ]
            for top, bottom, color, name in levels:
                fig.add_trace(go.Scatter(x=data['Date'], y=[top]*len(data), line=dict(width=0), showlegend=False, hoverinfo='skip'), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=[bottom]*len(data), fill='tonexty', fillcolor=color, line=dict(width=1, color='rgba(255,255,255,0.05)'), name=name), row=1, col=1)
            # 황금선 강조
            fig.add_trace(go.Scatter(x=data['Date'], y=[f618]*len(data), name="GOLDEN LINE (61.8%)", line=dict(color='gold', width=4)), row=1, col=1)

        # 캔들스틱
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        # 이동평균선
        if show_ma:
            for col, color in [('MA5', 'orange'), ('MA20', 'cyan'), ('MA60', 'magenta'), ('MA120', 'white')]:
                fig.add_trace(go.Scatter(x=data['Date'], y=data[col], name=col, line=dict(color=color, width=1.5)), row=1, col=1)

        # ★BUY 타점
        buy_pts = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buy_pts['Date'], y=buy_pts['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buy_pts), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='매수타점'), row=1, col=1)
        
        # 거래량
        if show_vol:
            fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='rgba(128,128,128,0.5)'), row=2, col=1)
            
        fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
