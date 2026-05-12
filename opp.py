import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import requests

# 1. 페이지 설정
st.set_page_config(page_title="Global Strategy Terminal", layout="wide")

# 2. [강력 수정] 네이버 금융/KRX 데이터를 활용한 전종목 리스트 강제 확보
@st.cache_data(show_spinner="한국 주식 전체 리스트를 동기화 중...")
def get_total_kr_stocks():
    try:
        # FinanceDataReader의 소스를 포함하여 2중으로 데이터를 확보합니다.
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Symbol', 'Name', 'Market']]
    except:
        # 만약 위 주소가 막히면 비상용 우량주 리스트라도 즉시 생성
        return pd.DataFrame([
            {"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"},
            {"Symbol": "000660", "Name": "SK하이닉스", "Market": "KOSPI"},
            {"Symbol": "005935", "Name": "삼성전자우", "Market": "KOSPI"},
            {"Symbol": "006400", "Name": "삼성SDI", "Market": "KOSPI"},
            {"Symbol": "009150", "Name": "삼성전기", "Market": "KOSPI"},
            {"Symbol": "207940", "Name": "삼성바이오로직스", "Market": "KOSPI"}
        ])

all_stocks = get_total_kr_stocks()

# 3. 전략 엔진 (피보나치 6단계 및 타점 - 기존 로직 100% 유지)
def apply_strategy(df):
    if len(df) < 20: return df
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    
    delta = df['Close'].diff()
    df['RSI'] = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean())))
    
    # 피보나치 6단계 계산
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_0'], df['Fib_236'], df['Fib_382'], df['Fib_500'], df['Fib_618'], df['Fib_100'] = \
        hp, hp - 0.236 * diff, hp - 0.382 * diff, hp - 0.500 * diff, hp - 0.618 * diff, lp
    
    # ★BUY 타점
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 4. 사이드바 (사용자가 원하시는 '전체 리스트 나열' 구현)
with st.sidebar:
    st.header("🔍 국/내외 종목 통합 검색")
    query = st.text_input("종목명 입력 (예: 삼성, 현대, 에코)", value="삼성")
    
    # [핵심] 검색어가 포함된 모든 국내 주식 리스트를 필터링하여 나열
    results = all_stocks[all_stocks['Name'].str.contains(query, na=False, case=False)]
    
    st.subheader(f"📋 '{query}' 검색 리스트 ({len(results)}건)")
    
    if not results.empty:
        # 모든 검색 결과를 표로 보여줌 (여기서 코드를 확인 가능)
        st.dataframe(results[['Name', 'Symbol', 'Market']].sort_values(by='Name'), hide_index=True, height=300)
        
        # 선택박스에 전체 검색 결과를 다 집어넣음
        options = [f"{r['Name']} ({r['Symbol']})" for _, r in results.sort_values(by='Name').iterrows()]
        selected_choice = st.selectbox("분석할 종목을 고르세요", options)
        
        target_code = selected_choice.split("(")[1].replace(")", "")
        m_info = results[results['Symbol'] == target_code].iloc[0]['Market']
        ticker = f"{target_code}{'.KS' if m_info == 'KOSPI' else '.KQ'}"
        final_name = selected_choice.split(" (")[0]
    else:
        st.warning("국내 리스트에 없습니다. 미국 티커(예: TSLA)를 입력하세요.")
        ticker = query.upper()
        final_name = query.upper()

    st.divider()
    period = st.selectbox("기간", ["6mo", "1y", "2y"])
    show_fib = st.checkbox("피보나치 채널 표시", value=True)

# 5. 메인 리포트 (기존 기능 100% 유지)
if ticker:
    data = yf.download(ticker, period=period, interval="1d", auto_adjust=True)
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = apply_strategy(data)
        
        f = {k: data[k].iloc[-1] for k in ['Fib_0', 'Fib_236', 'Fib_382', 'Fib_500', 'Fib_618', 'Fib_100']}
        curr = float(data['Close'].iloc[-1])
        
        st.title(f"📊 {final_name} ({ticker})")
        
        # 상단 메트릭 가이드
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("현재가", f"{curr:,.0f}")
        col2.metric("강력매수(61.8%)", f"{f['Fib_618']:,.0f}", f"{((f['Fib_618']/curr)-1)*100:.1f}%")
        col3.metric("수익실현(38.2%)", f"{f['Fib_382']:,.0f}", f"{((f['Fib_382']/curr)-1)*100:.1f}%")
        col4.metric("손절(LP)", f"{f['Fib_100']:,.0f}", f"{((f['Fib_100']/curr)-1)*100:.1f}%", delta_color="inverse")

        # 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
        
        if show_fib:
            # 채널 시각화
            colors = ['rgba(255,0,0,0.1)', 'rgba(255,165,0,0.1)', 'rgba(255,255,0,0.05)', 'rgba(0,255,0,0.1)', 'rgba(0,0,255,0.1)']
            lev_list = [f['Fib_0'], f['Fib_236'], f['Fib_382'], f['Fib_500'], f['Fib_618'], f['Fib_100']]
            for i in range(5):
                fig.add_trace(go.Scatter(x=data['Date'], y=[lev_list[i]]*len(data), line=dict(width=0), showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=data['Date'], y=[lev_list[i+1]]*len(data), fill='tonexty', fillcolor=colors[i], line=dict(width=0.5, color='white'), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['Date'], y=[f['Fib_618']]*len(data), name="GOLDEN LINE", line=dict(color='gold', width=4)), row=1, col=1)

        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        # ★BUY 타점
        buy = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buy['Date'], y=buy['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buy), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='매수타점'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='gray'), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
