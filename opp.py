import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="Custom Strategy Terminal", layout="wide")

# 2. [핵심] 네이버/KRX 기준 전종목 리스트 확보 (절대 누락 방지)
@st.cache_data(show_spinner="전종목 리스트 동기화 중...")
def get_total_krx_data():
    try:
        # 한국거래소(KRX) 전체 종목 리스트 소스
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Symbol', 'Name', 'Market']]
    except:
        # 서버 응답 없을 시 비상용 (최소 데이터)
        return pd.DataFrame([{"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"}])

krx_total = get_total_kr_stocks() if 'get_total_kr_stocks' in globals() else get_total_krx_data()

# 3. 전략 엔진 (기존 피보나치 6단계 + RSI + ★BUY 타점 로직)
def apply_full_strategy(df):
    if len(df) < 20: return df
    
    # 이평선
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 피보나치 6단계 (고점/저점 기준)
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_0'] = hp
    df['Fib_236'] = hp - 0.236 * diff
    df['Fib_382'] = hp - 0.382 * diff
    df['Fib_500'] = hp - 0.500 * diff
    df['Fib_618'] = hp - 0.618 * diff
    df['Fib_100'] = lp
    
    # ★BUY 타점
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 4. 사이드바: 전종목 리스트 나열 및 종목 선택
with st.sidebar:
    st.header("🔍 국/내외 통합 검색")
    u_input = st.text_input("종목명 또는 티커 입력", value="삼성")
    
    # [검색 기능] 입력어가 포함된 모든 국내 종목 나열
    res = krx_total[krx_total['Name'].str.contains(u_input, na=False, case=False)]
    
    if not res.empty:
        st.subheader(f"📋 '{u_input}' 검색 결과 ({len(res)}건)")
        # 표로 전체 리스트와 코드 출력
        st.dataframe(res[['Name', 'Symbol', 'Market']].sort_values('Name'), hide_index=True, height=300)
        
        # 분석 대상 선택
        opts = [f"{r['Name']} ({r['Symbol']})" for _, r in res.sort_values('Name').iterrows()]
        sel = st.selectbox("분석 종목 선택", opts)
        
        t_code = sel.split("(")[1].replace(")", "")
        t_market = res[res['Symbol'] == t_code].iloc[0]['Market']
        final_ticker = f"{t_code}{'.KS' if t_market == 'KOSPI' else '.KQ'}"
        final_name = sel.split(" (")[0]
    else:
        st.info("해외 티커로 분석합니다.")
        final_ticker = u_input.upper()
        final_name = u_input.upper()

    st.divider()
    period = st.selectbox("분석 기간", ["6mo", "1y", "2y"])
    show_fib = st.checkbox("피보나치 채널 표시", value=True)

# 5. 메인 리포트 화면 (피보나치 수치 및 차트 직접 생성)
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = apply_full_strategy(data)
        
        # 마지막 피보나치 값들
        f_vals = {k: data[k].iloc[-1] for k in ['Fib_0', 'Fib_236', 'Fib_382', 'Fib_500', 'Fib_618', 'Fib_100']}
        curr = float(data['Close'].iloc[-1])
        
        st.title(f"📊 {final_name} ({final_ticker}) 전략 분석")
        
        # 상단 메수/매도 목표가 메트릭 (기존 기능)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("현재가", f"{curr:,.0f}")
        m2.metric("강력지지(61.8%)", f"{f_vals['Fib_618']:,.0f}", f"{((f_vals['Fib_618']/curr)-1)*100:.1f}%")
        m3.metric("수익실현(38.2%)", f"{f_vals['Fib_382']:,.0f}", f"{((f_vals['Fib_382']/curr)-1)*100:.1f}%")
        m4.metric("손절가(LP)", f"{f_vals['Fib_100']:,.0f}", f"{((f_vals['Fib_100']/curr)-1)*100:.1f}%", delta_color="inverse")

        # 차트 생성 (Plotly)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
        
        # 피보나치 채널 시각화 (기존 로직)
        if show_fib:
            colors = ['rgba(255,0,0,0.1)', 'rgba(255,165,0,0.1)', 'rgba(255,255,0,0.05)', 'rgba(0,255,0,0.1)', 'rgba(0,0,255,0.1)']
            lev_keys = ['Fib_0', 'Fib_236', 'Fib_382', 'Fib_500', 'Fib_618', 'Fib_100']
            for i in range(5):
                fig.add_trace(go.Scatter(x=data['Date'], y=[f_vals[lev_keys[i]]]*len(data), line=dict(width=0), showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=[f_vals[lev_keys[i+1]]]*len(data), fill='tonexty', fillcolor=colors[i], line=dict(width=0.5, color='rgba(255,255,255,0.1)'), showlegend=False), row=1, col=1)
            # 골든라인 강조
            fig.add_trace(go.Scatter(x=data['Date'], y=[f_vals['Fib_618']]*len(data), name="GOLDEN LINE", line=dict(color='gold', width=4)), row=1, col=1)

        # 캔들스틱 차트
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        # ★BUY 타점 표시
        buys = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buys['Date'], y=buys['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buys), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='매수타점'), row=1, col=1)
        
        # 거래량
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='gray'), row=2, col=1)
        
        fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
