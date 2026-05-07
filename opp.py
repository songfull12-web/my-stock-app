import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Professional Stock Terminal", layout="wide")

# 2. 종목 데이터 로드 (KRX 종목 리스트 - 백업 로직 포함)
@st.cache_data
def get_stock_dict():
    # 기본 하드코딩 백업 (네트워크 오류 대비)
    stocks = {"삼성전자": "005930", "SK하이닉스": "000660", "현대차": "005380", "NAVER": "035420", "카카오": "035720"}
    try:
        # KRX 전체 종목 데이터 수집
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        # 필요한 컬럼만 추출하여 딕셔너리화
        for _, row in df.iterrows():
            stocks[str(row['Name'])] = str(row['Symbol']).zfill(6)
    except Exception as e:
        st.sidebar.error(f"종목 리스트 로드 실패 (기본 종목만 사용 가능): {e}")
    return stocks

stock_dict = get_stock_dict()

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 엔진")
    search_input = st.text_input("종목명 또는 티커 입력", value="삼성전자").strip()
    
    final_ticker = ""
    selected_name = search_input # 기본값

    # 검색 로직 개선
    matches = [name for name in stock_dict.keys() if search_input in name]
    
    if matches:
        selected_name = st.selectbox(f"'{search_input}' 검색 결과", matches)
        code = stock_dict[selected_name]
        # 한국 주식은 숫자로 된 코드이므로 .KS(코스피) 붙여서 시작
        final_ticker = f"{code}.KS" if code.isdigit() else code
    else:
        # 검색 결과가 없으면 사용자가 입력한 값을 그대로 티커로 사용 (예: AAPL, 005930 등)
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
    show_fib = st.checkbox("피보나치 구역", value=True)

# 4. 분석 계산 함수
def add_indicators(df):
    if len(df) < 60: return df # 데이터 부족 시 리턴
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 신호 로직
    df['Buy_Signal'] = (df['RSI'] < 35) | ((df['MA20'] > df['MA60']) & (df['MA20'].shift(1) <= df['MA60'].shift(1)))
    df['Sell_Signal'] = (df['RSI'] > 65) | ((df['MA20'] < df['MA60']) & (df['MA20'].shift(1) >= df['MA60'].shift(1)))
    return df

# 5. 메인 출력 영역
if final_ticker:
    try:
        # yfinance 데이터 호출 (KOSPI -> KOSDAQ 순차 시도)
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

            # 📋 상단 핵심 대시보드
            st.title(f"📊 {selected_name} ({final_ticker})")
            m_cols = st.columns(4)
            with m_cols[0]: st.metric("현재가", f"{curr_p:,.0f}")
            with m_cols[1]: st.metric("전고점(타겟)", f"{high_v:,.0f}", f"{((high_v/curr_p)-1)*100:.1f}%")
            with m_cols[2]: st.metric("전저점(지지)", f"{low_v:,.0f}", f"{((low_v/curr_p)-1)*100:.1f}%", delta_color="normal")
            with m_cols[3]: st.metric("RSI 지수", f"{rsi_val:.1f}")

            st.divider()

            # 차트 레이아웃
            rows = 2 if show_rsi or show_vol else 1
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                               row_heights=[0.7, 0.3] if rows == 2 else [1.0],
                               specs=[[{"secondary_y": True}], [{"secondary_y": False}]] if rows == 2 else [[{"secondary_y": True}]])

            # 캔들차트
            fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], 
                                       low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

            # 매수/매도 타이밍
            if show_signals:
                buy_pts = data[data.get('Buy_Signal', False)]
                sell_pts = data[data.get('Sell_Signal', False)]
                fig.add_trace(go.Scatter(x=buy_pts.iloc[:,0], y=buy_pts['Low']*0.98, mode='markers', 
                                         name='매수', marker=dict(symbol='triangle-up', size=12, color='#00FF00')), row=1, col=1)
                fig.add_trace(go.Scatter(x=sell_pts.iloc[:,0], y=sell_pts['High']*1.02, mode='markers', 
                                         name='매도', marker=dict(symbol='triangle-down', size=12, color='#FF0000')), row=1, col=1)

            # 이평선
            if show_ma:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA20'], name="20일선", line=dict(color='cyan', width=1.2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA60'], name="60일선", line=dict(color='magenta', width=1.2)), row=1, col=1)

            # 추세 지지/저항선
            if show_trend:
                y_v, x_v = data['Close'].values, np.arange(len(data))
                slope, intercept, _, _, std_err = linregress(x_v, y_v)
                if slope > 0:
                    line = (intercept + slope * x_v) - (std_err * 12)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=line, name="상승지지", line=dict(color='#00FF00', width=1.5, dash='dot')), row=1, col=1)
                else:
                    line = (intercept + slope * x_v) + (std_err * 12)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=line, name="하락저항", line=dict(color='#FF0000', width=1.5, dash='dot')), row=1, col=1)

            # 하단 보조지표
            if show_vol:
                v_colors = ['red' if r['Open'] < r['Close'] else 'blue' for _, r in data.iterrows()]
                fig.add_trace(go.Bar(x=data.iloc[:,0], y=data['Volume'], name="거래량", marker_color=v_colors, opacity=0.4), row=rows, col=1)
            if show_rsi:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#FFD700')), row=rows, col=1)

            fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            # 정보 출처
            st.caption(f"Data Source: Yahoo Finance | Ticker: {final_ticker}")

        else:
            st.error(f"'{final_ticker}' 데이터를 불러오지 못했습니다. 종목코드나 인터넷 연결을 확인해주세요.")
    except Exception as e:
        st.error(f"오류 발생: {e}")

# 하단 캡션
st.info("💡 팁: 검색어 입력 후 엔터를 치면 '검색 결과' 선택 박스가 업데이트됩니다.")
