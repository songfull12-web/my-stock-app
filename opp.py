import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="Global Strategy Terminal", layout="wide")

# 2. 국내주식 전체 리스트 로드 (이 데이터로 전체 나열을 수행합니다)
@st.cache_data
def get_krx_all():
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        return pd.read_csv(url)[['Symbol', 'Name', 'Market']]
    except:
        return pd.DataFrame([{"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"}])

krx_list = get_krx_all()

# 3. 보조지표 및 전략 엔진 (기존 로직 그대로 유지)
def add_indicators(df):
    if len(df) < 20: return df
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    df['MA120'] = df['Close'].rolling(120).mean()
    
    delta = df['Close'].diff()
    df['RSI'] = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean())))
    
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_0'], df['Fib_236'], df['Fib_382'], df['Fib_500'], df['Fib_618'], df['Fib_100'] = \
        hp, hp - 0.236 * diff, hp - 0.382 * diff, hp - 0.500 * diff, hp - 0.618 * diff, lp
    
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 4. 사이드바 구성 (검색 및 리스트 나열)
with st.sidebar:
    st.header("🔍 국/내외 종목 통합 검색")
    search_val = st.text_input("종목명 또는 티커 입력", value="삼성")
    
    # [핵심 추가] 국내주식 전체 리스트 나열 기능
    st.subheader("📋 국내주식 전체 검색 결과")
    matches = krx_list[krx_list['Name'].str.contains(search_val, na=False)]
    
    if not matches.empty:
        # 검색된 모든 종목을 표로 나열 (코드를 바로 볼 수 있게)
        st.dataframe(matches[['Name', 'Symbol', 'Market']], hide_index=True, height=300)
        
        # 분석 대상 선택 (리스트 중 하나 선택)
        options = [f"{r['Name']} ({r['Symbol']})" for _, r in matches.iterrows()]
        choice = st.selectbox("분석할 종목 선택", options)
        
        target_symbol = choice.split("(")[1].replace(")", "")
        market_info = matches[matches['Symbol'] == target_symbol].iloc[0]['Market']
        suffix = ".KS" if market_info == 'KOSPI' else ".KQ"
        final_ticker = f"{target_symbol}{suffix}"
        display_name = choice.split(" (")[0]
    else:
        st.info("국내 검색 결과 없음 -> 해외 티커로 인식")
        final_ticker = search_val.upper()
        display_name = search_val.upper()

    st.divider()
    period = st.selectbox("기간", ["6mo", "1y", "2y"], index=0)
    show_fib = st.checkbox("피보나치 채널 표시", value=True)

# 5. 메인 영역 (차트 및 가이드 로직 100% 유지)
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_indicators(data)
        
        f0, f236, f382, f500, f618, f100 = data['Fib_0'].iloc[-1], data['Fib_236'].iloc[-1], data['Fib_382'].iloc[-1], data['Fib_500'].iloc[-1], data['Fib_618'].iloc[-1], data['Fib_100'].iloc[-1]
        curr_p = float(data['Close'].iloc[-1])
        
        st.title(f"📊 {display_name} ({final_ticker}) 분석 리포트")
        
        # [기존 기능] 상단 가이드 메트릭
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가", f"{curr_p:,.0f}")
        c2.metric("강력지지(61.8%)", f"{f618:,.0f}", f"{((f618/curr_p)-1)*100:.1f}%")
        c3.metric("목표가(38.2%)", f"{f382:,.0f}", f"{((f382/curr_p)-1)*100:.1f}%")
        c4.metric("손절가(LP)", f"{f100:,.0f}", f"{((f100/curr_p)-1)*100:.1f}%", delta_color="inverse")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
        
        # [기존 기능] 피보나치 채널 색상
        if show_fib:
            levels = [(f0, f236, 'rgba(255, 0, 0, 0.1)'), (f236, f382, 'rgba(255, 165, 0, 0.1)'), (f382, f500, 'rgba(255, 255, 0, 0.05)'), (f500, f618, 'rgba(0, 255, 0, 0.1)'), (f618, f100, 'rgba(0, 0, 255, 0.1)')]
            for top, bottom, color in levels:
                fig.add_trace(go.Scatter(x=data['Date'], y=[top]*len(data), line=dict(width=0), showlegend=False, hoverinfo='skip'), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=[bottom]*len(data), fill='tonexty', fillcolor=color, line=dict(width=0.5, color='white'), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['Date'], y=[f618]*len(data), name="GOLDEN LINE", line=dict(color='gold', width=4)), row=1, col=1)

        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        # [기존 기능] ★BUY 타점
        buy_pts = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buy_pts['Date'], y=buy_pts['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buy_pts), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='타점'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='gray'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
