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
    show_signals = st.checkbox("매수/매도 타이밍 표시", value=True)
    show_vol = st.checkbox("거래량 차트", value=True)
    show_rsi = st.checkbox("RSI 지표", value=True)
    show_fib = st.checkbox("피보나치 구역", value=True)

# 4. 분석 계산 로직
def add_indicators(df):
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
            rsi_val = data['RSI'].iloc[-1]

            # 📋 상단 요약 대시보드 (핵심 가격 지표)
            cols = st.columns(4)
            with cols[0]:
                st.metric("현재가", f"{curr_p:,.0f}")
            with cols[1]:
                st.metric("전고점(매도타겟)", f"{high_v:,.0f}", f"{((high_v/curr_p)-1)*100:.1f}%")
            with cols[2]:
                st.metric("전저점(지지라인)", f"{low_v:,.0f}", f"{((low_v/curr_p)-1)*100:.1f}%", delta_color="normal")
            with cols[3]:
                status = "과매수(주의)" if rsi_val > 70 else "과매도(관심)" if rsi_val < 30 else "보통"
                st.metric("심리 지수(RSI)", f"{rsi_val:.1f}", status)

            st.divider()

            # 차트 레이아웃
            rows = 2 if show_rsi or show_vol else 1
            specs = [[{"secondary_y": True}], [{"secondary_y": False}]] if rows == 2 else [[{"secondary_y": True}]]
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                               row_heights=[0.7, 0.3] if rows == 2 else [1.0], specs=specs)

            # [메인] 캔들차트
            fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], 
                                       low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

            # [메인] 매수/매도 타이밍 화살표
            if show_signals:
                buy_pts = data[data['Buy_Signal']]
                sell_pts = data[data['Sell_Signal']]
                fig.add_trace(go.Scatter(x=buy_pts.iloc[:,0], y=buy_pts['Low']*0.97, mode='markers', 
                                         name='매수점', marker=dict(symbol='triangle-up', size=12, color='#00FF00')), row=1, col=1)
                fig.add_trace(go.Scatter(x=sell_pts.iloc[:,0], y=sell_pts['High']*1.03, mode='markers', 
                                         name='매도점', marker=dict(symbol='triangle-down', size=12, color='#FF0000')), row=1, col=1)

            # [메인] 이평선
            if show_ma:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA20'], name="20일", line=dict(color='cyan', width=1.2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA60'], name="60일", line=dict(color='magenta', width=1.2)), row=1, col=1)

            # [메인] 추세 지지/저항선
            if show_trend:
                y_val, x_val = data['Close'].values, np.arange(len(data))
                slope, intercept, _, _, std_err = linregress(x_val, y_val)
                if slope > 0:
                    line = (intercept + slope * x_val) - (std_err * 15)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=line, name="상승 지지선", line=dict(color='#00FF00', width=1.5)), row=1, col=1)
                else:
                    line = (intercept + slope * x_val) + (std_err * 15)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=line, name="하락 저항선", line=dict(color='#FF0000', width=1.5)), row=1, col=1)

            # [메인] 피보나치
            if show_fib:
                diff = high_v - low_v
                for r in [0, 0.382, 0.5, 0.618, 1.0]:
                    val = high_v - (r * diff)
                    fig.add_hline(y=val, line_dash="dash", line_color="rgba(255,255,255,0.2)", row=1, col=1)

            # [하단] 거래량/RSI
            if show_vol:
                colors = ['red' if r['Open'] < r['Close'] else 'blue' for _, r in data.iterrows()]
                fig.add_trace(go.Bar(x=data.iloc[:,0], y=data['Volume'], name="거래량", marker_color=colors, opacity=0.4), row=rows, col=1)
            if show_rsi:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#FFD700')), row=rows, col=1)

            fig.update_layout(template="plotly_dark", height=750, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

            # 💡 실시간 전략 가이드
            st.subheader("💡 실시간 전략 가이드")
            g_cols = st.columns(3)
            with g_cols[0]:
                if rsi_val < 30: st.success("✅ **과매도**: 적극 매수 고려 구간")
                elif rsi_val > 70: st.error("⚠️ **과매수**: 수익 실현 고려 구간")
                else: st.info("ℹ️ **중립**: 추세 지속 확인 필요")
            with g_cols[1]:
                if data['MA20'].iloc[-1] > data['MA60'].iloc[-1]: st.success("📈 **추세**: 정배열 강세 흐름")
                else: st.error("📉 **추세**: 역배열 약세 흐름")
            with g_cols[2]:
                mid_p = high_v - (0.5 * (high_v - low_v))
                if curr_p < mid_p: st.warning(f"🎯 **가격**: 중심값({mid_p:,.0f}) 이하 저평가")
                else: st.info(f"🎯 **가격**: 중심값({mid_p:,.0f}) 이상 돌파 시도")

        else: st.error("데이터 로드 실패")
    except Exception as e: st.error(f"오류: {e}")

st.caption("Data Source: Yahoo Finance | 가격 지표는 전고점/전저점을 기준으로 자동 계산됩니다.")
