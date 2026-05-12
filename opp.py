import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# [1] 페이지 설정
st.set_page_config(page_title="Global Strategy Terminal", layout="wide")

# [2] 전종목 데이터베이스 로드 (실행 검토 완료)
@st.cache_data(show_spinner="전종목 데이터를 실시간 동기화 중...")
def load_krx_master_db():
    try:
        # 가장 안정적인 KRX 상장사 리스트 소스 (FinanceDataReader 기반)
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Symbol', 'Name', 'Market']].dropna()
    except:
        # 비상용 기본 데이터
        return pd.DataFrame([{"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"}])

master_db = load_krx_master_db()

# [3] 전략 로직 엔진 (피보나치 6단계 및 타점 - 검토 완료)
def apply_trading_strategy(df):
    if len(df) < 20: return df
    
    # 이평선
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 피보나치 6단계 (HP/LP 기준)
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

# [4] 사이드바 레이아웃 (네이버식 검색 구현)
with st.sidebar:
    st.header("🔍 전종목 통합 검색")
    query = st.text_input("종목명 일부 입력 (예: 삼성, 에코)", value="삼성")
    
    # 입력된 텍스트가 포함된 모든 국내 종목 필터링
    matches = master_db[master_db['Name'].str.contains(query, na=False, case=False)]
    
    if not matches.empty:
        st.subheader(f"📋 '{query}' 관련 리스트 ({len(matches)}건)")
        # 표 형태로 전체 나열 (코드를 확인하기 위함)
        st.dataframe(matches[['Name', 'Symbol', 'Market']].sort_values('Name'), hide_index=True, height=350)
        
        # 실제 분석할 종목 선택
        options = [f"{r['Name']} ({r['Symbol']})" for _, r in matches.sort_values('Name').iterrows()]
        pick = st.selectbox("분석할 종목을 고르세요", options)
        
        # 티커 변환 로직
        s_code = pick.split("(")[1].replace(")", "")
        m_info = matches[matches['Symbol'] == s_code].iloc[0]['Market']
        target_ticker = f"{s_code}{'.KS' if m_info == 'KOSPI' else '.KQ'}"
        target_name = pick.split(" (")[0]
    else:
        st.warning("국내 종목 없음. 해외 티커 모드 가동.")
        target_ticker = query.upper()
        target_name = query.upper()

    st.divider()
    period = st.selectbox("차트 기간", ["6mo", "1y", "2y"])
    show_fib = st.checkbox("피보나치 채널 강조", value=True)

# [5] 메인 리포트 & 차트 시각화
if target_ticker:
    # 데이터 로드 시 멀티인덱스 오류 방지 로직 포함
    data = yf.download(target_ticker, period=period, interval="1d", auto_adjust=True)
    
    if not data.empty:
        # 데이터 정제
        if isinstance(data.columns, pd.MultiIndex): 
            data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = apply_trading_strategy(data)
        
        # 마지막 지표값
        f = {k: data[k].iloc[-1] for k in ['Fib_0', 'Fib_236', 'Fib_382', 'Fib_500', 'Fib_618', 'Fib_100']}
        curr = float(data['Close'].iloc[-1])
        
        st.title(f"📊 {target_name} ({target_ticker}) 전략 분석")
        
        # 상단 핵심 가격 지표
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가", f"{curr:,.0f}")
        c2.metric("강력지지(61.8%)", f"{f['Fib_618']:,.0f}", f"{((f['Fib_618']/curr)-1)*100:.1f}%")
        c3.metric("수익목표(38.2%)", f"{f['Fib_382']:,.0f}", f"{((f['Fib_382']/curr)-1)*100:.1f}%")
        c4.metric("손절가(LP)", f"{f['Fib_100']:,.0f}", f"{((f['Fib_100']/curr)-1)*100:.1f}%", delta_color="inverse")

        # 메인 차트 생성
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
        
        # 피보나치 채널 배경 (검토 완료)
        if show_fib:
            levels = [
                (f['Fib_0'], f['Fib_236'], 'rgba(255, 0, 0, 0.1)'),
                (f['Fib_236'], f['Fib_382'], 'rgba(255, 165, 0, 0.1)'),
                (f['Fib_382'], f['Fib_500'], 'rgba(255, 255, 0, 0.05)'),
                (f['Fib_500'], f['Fib_618'], 'rgba(0, 255, 0, 0.1)'),
                (f['Fib_618'], f['Fib_100'], 'rgba(0, 0, 255, 0.1)')
            ]
            for top, bottom, color in levels:
                fig.add_trace(go.Scatter(x=data['Date'], y=[top]*len(data), line=dict(width=0), showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=[bottom]*len(data), fill='tonexty', fillcolor=color, line=dict(width=0.5, color='rgba(255,255,255,0.05)'), showlegend=False), row=1, col=1)
            # 골든라인 강조
            fig.add_trace(go.Scatter(x=data['Date'], y=[f['Fib_618']]*len(data), name="GOLDEN LINE", line=dict(color='gold', width=4)), row=1, col=1)

        # 캔들스틱 및 ★BUY 타점
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        buys = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buys['Date'], y=buys['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buys), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='매수타점'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='gray'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
