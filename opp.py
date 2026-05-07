import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Professional Stock Terminal", layout="wide")

# 2. 종목 데이터 로드
@st.cache_data
def get_stock_dict():
    stocks = {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS"}
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        for _, row in df.iterrows():
            stocks[row['Name']] = row['Symbol']
    except:
        pass
    return stocks

stock_dict = get_stock_dict()

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 엔진")
    search_input = st.text_input("종목명 입력", value="삼성전자").strip()
    
    final_ticker = ""
    if search_input:
        matches = [name for name in stock_dict.keys() if search_input in name]
        if matches:
            selected_name = st.selectbox("종목 선택", matches)
            code = stock_dict[selected_name]
            final_ticker = f"{code}.KS" if code.isdigit() else code
        else:
            final_ticker = search_input.upper()

    st.divider()
    interval = st.selectbox("차트 주기", ["60m", "1d", "1wk", "1mo"], index=1)
    period = st.selectbox("조회 기간", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
    
    st.subheader("🛠️ 지표 커스텀")
    show_ma = st.checkbox("이동평균선(MA)", value=True)
    show_trend = st.checkbox("추세 지지/저항선", value=True)
    show_signals = st.checkbox("매수/매도 타이밍 표시", value=True) # 신규 추가
    show_vol = st.checkbox("거래량 차트", value=True)
    show_rsi = st.checkbox("RSI 지표", value=True)
    show_fib = st.checkbox("피보나치 구역", value=True)

# 4. 분석 및 신호 계산 로직
def add_indicators(df):
    # 이동평균선
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 매수/매도 신호 로직 (단순화된 퀀트 전략)
    # 매수: RSI < 35 (과매도) 또는 골든크로스(MA20 > MA60) 시작점
    df['Buy_Signal'] = (df['RSI'] < 35) | ((df['MA20'] > df['MA60']) & (df['MA20'].shift(1) <= df['MA60'].shift(1)))
    # 매도: RSI > 65 (과매수) 또는 데드크로스(MA20 < MA60) 시작점
    df['Sell_Signal'] = (df['RSI'] > 65) | ((df['MA20'] < df['MA60']) & (df['MA20'].shift(1) >= df['MA60'].shift(1)))
    
    return df

# 5. 메인 출력
if final_ticker:
    try:
        data = yf.download(final_ticker, period=period, interval=interval, auto_adjust=True)
        if data.empty and ".KS" in final_ticker:
            data = yf.download(final_ticker.replace(".KS", ".KQ"), period=period, interval=interval, auto_adjust=True)

        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            data = add_indicators(data)
            
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            
            rows = 2 if show_rsi or show_vol else 1
            specs = [[{"secondary_y": True}], [{"secondary_y": False}]] if rows == 2 else [[{"secondary_y": True}]]
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                               row_heights=[0.7, 0.3] if rows == 2 else [1.0], specs=specs)

            # [메인] 캔들차트
            fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], 
                                       low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

            # [메인] 매수/매도 화살표 신호
            if show_signals:
                buy_points = data[data['Buy_Signal']]
                sell_points = data[data['Sell_Signal']]
                
                fig.add_trace(go.Scatter(x=buy_points.iloc[:,0], y=buy_points['Low'] * 0.98,
                                         mode='markers', name='매수 신호',
                                         marker=dict(symbol='triangle-up', size=12, color='#00FF00')), row=1, col=1)
                
                fig.add_trace(go.Scatter(x=sell_points.iloc[:,0], y=sell_points['High'] * 1.02,
                                         mode='markers', name='매도 신호',
                                         marker=dict(symbol='triangle-down', size=12, color='#FF0000')), row=1, col=1)

            # [메인] 이평선
            if show_ma:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA20'], name="20일", line=dict(color='cyan', width=1.2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA60'], name="60일", line=dict(color='magenta', width=1.2)), row=1, col=1)

            # [메인] 추세 지지/저항선
            if show_trend:
                y = data['Close'].values
                x = np.arange(len(y))
                slope, intercept, r_value, p_value, std_err = linregress(x, y)
                if slope > 0:
                    support_line = (intercept + slope * x) - (std_err * 15)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=support_line, name="상승 지지", line=dict(color='#00FF00', width=1.5, dash='solid')), row=1, col=1)
                else:
                    resistance_line = (intercept + slope * x) + (std_err * 15)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=resistance_line, name="하락 저항", line=dict(color='#FF0000', width=1.5, dash='solid')), row=1, col=1)

            # [메인] 피보나치
            if show_fib:
                diff = high_v - low_v
                levels = [0, 0.382, 0.5, 0.618, 1.0]
                for r in levels:
                    val = high_v - (r * diff)
                    fig.add_hline(y=val, line_dash="dash", line_color="rgba(255, 255, 255, 0.2)", row=1, col=1)

            # [하단] 거래량 또는 RSI
            if show_vol:
                vol_colors = ['red' if row['Open'] < row['Close'] else 'blue' for _, row in data.iterrows()]
                fig.add_trace(go.Bar(x=data.iloc[:,0], y=data['Volume'], name="거래량", marker_color=vol_colors, opacity=0.4), row=rows, col=1)
            
            if show_rsi:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#FFD700', width=1.5)), row=rows, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="#FF6347", row=rows, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="#32CD32", row=rows, col=1)

            fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

            # 📋 실시간 투자 전략 가이드 (신규 추가)
            st.subheader("💡 실시간 전략 가이드")
            st.divider()
            
            last_rsi = data['RSI'].iloc[-1]
            last_ma20 = data['MA20'].iloc[-1]
            last_ma60 = data['MA60'].iloc[-1]
            
            advice_cols = st.columns(3)
            with advice_cols[0]:
                if last_rsi < 30:
                    st.success("✅ **매수 검토 (과매도)**: 현재 심리가 매우 위축되어 있습니다. 분할 매수 시점입니다.")
                elif last_rsi > 70:
                    st.error("⚠️ **매도 검토 (과매수)**: 과열 구간입니다. 익절 혹은 비중 축소를 고려하세요.")
                else:
                    st.info("ℹ️ **관망**: 심리 지수가 보통 수준입니다. 추세를 더 지켜보세요.")
            
            with advice_cols[1]:
                if last_ma20 > last_ma60:
                    st.success("📈 **추세: 정배열 (강세)**: 단기 이동평균선이 상단에 위치한 우상향 흐름입니다.")
                else:
                    st.error("📉 **추세: 역배열 (약세)**: 하락 추세가 진행 중이거나 저항을 받고 있습니다.")
                    
            with advice_cols[2]:
                fib_05 = high_v - (0.5 * (high_v - low_v))
                if curr_p < fib_05:
                    st.warning(f"🎯 **가격 위치**: 고점 대비 중심값({fib_05:,.0f}) 아래에 있어 가격 매력이 있습니다.")
                else:
                    st.info(f"🎯 **가격 위치**: 고점 대비 중심값({fib_05:,.0f}) 위에 있어 돌파 여부를 확인하세요.")

        else: st.error("데이터 로드 실패")
    except Exception as e: st.error(f"오류 발생: {e}")

st.caption("Data Source: Yahoo Finance | 매수/매도 신호는 RSI 및 이평선 교차 기반의 참고용 지표입니다.")
