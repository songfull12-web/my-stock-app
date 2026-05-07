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
    show_trend = st.checkbox("추세 지지/저항선", value=True) # 기능 업데이트
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

            # [메인] 이평선
            if show_ma:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA20'], name="20일", line=dict(color='cyan', width=1.2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA60'], name="60일", line=dict(color='magenta', width=1.2)), row=1, col=1)

            # [메인] 추세 지지/저항선 로직
            if show_trend:
                y = data['Close'].values
                x = np.arange(len(y))
                slope, intercept, r_value, p_value, std_err = linregress(x, y)
                
                # 상승 추세 (기울기 > 0): 저점을 연결하는 지지선 역할
                if slope > 0:
                    support_line = (intercept + slope * x) - (std_err * 15) # 통계적 하단 편차 적용
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=support_line, name="상승 지지선", 
                                             line=dict(color='#00FF00', width=2, dash='solid')), row=1, col=1)
                # 하락 추세 (기울기 < 0): 고점을 연결하는 저항선 역할
                else:
                    resistance_line = (intercept + slope * x) + (std_err * 15) # 통계적 상단 편차 적용
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=resistance_line, name="하락 저항선", 
                                             line=dict(color='#FF0000', width=2, dash='solid')), row=1, col=1)

            # [메인] 피보나치 개선
            if show_fib:
                diff = high_v - low_v
                levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                colors = ["rgba(255, 99, 132, 0.07)", "rgba(255, 159, 64, 0.07)", "rgba(255, 205, 86, 0.07)", 
                          "rgba(75, 192, 192, 0.07)", "rgba(54, 162, 235, 0.07)", "rgba(153, 102, 255, 0.07)"]
                
                for i in range(len(levels)):
                    val = high_v - (levels[i] * diff)
                    fig.add_hline(y=val, line_dash="dash", line_color="rgba(255, 255, 255, 0.2)", line_width=1, row=1, col=1)
                    fig.add_annotation(x=data.iloc[:,0].iloc[0], y=val, text=f" {levels[i]*100}%",
                                       showarrow=False, xanchor="left", bgcolor="rgba(30, 30, 30, 0.8)",
                                       font=dict(size=9, color="gray"), row=1, col=1)
                    if i < len(levels) - 1:
                        fig.add_hrect(y0=high_v-(levels[i+1]*diff), y1=high_v-(levels[i]*diff), 
                                      fillcolor=colors[i % len(colors)], line_width=0, row=1, col=1)

            # [하단] 거래량 또는 RSI
            if show_vol:
                vol_colors = ['red' if row['Open'] < row['Close'] else 'blue' for _, row in data.iterrows()]
                fig.add_trace(go.Bar(x=data.iloc[:,0], y=data['Volume'], name="거래량", marker_color=vol_colors, opacity=0.4), row=rows, col=1)
            
            if show_rsi:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#FFD700', width=1.5)), row=rows, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="#FF6347", row=rows, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="#32CD32", row=rows, col=1)

            fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False,
                              margin=dict(l=10, r=10, t=50, b=10),
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True)

            # 📋 투자 전략 대시보드
            st.divider()
            cols = st.columns(4)
            with cols[0]: st.metric("현재가", f"{curr_p:,.0f}")
            with cols[1]: st.metric("기간 고점", f"{high_v:,.0f}", f"{((high_v/curr_p)-1)*100:.1f}%")
            with cols[2]: st.metric("기간 저점", f"{low_v:,.0f}", f"{((low_v/curr_p)-1)*100:.1f}%", delta_color="normal")
            with cols[3]:
                if show_rsi:
                    rsi_val = data['RSI'].iloc[-1]
                    status = "과매수(주의)" if rsi_val > 70 else "과매도(관심)" if rsi_val < 30 else "보통"
                    st.metric("심리 지수(RSI)", f"{rsi_val:.1f}", status)

        else: st.error("데이터 로드 실패")
    except Exception as e: st.error(f"오류 발생: {e}")

# 정보 출처 표시
st.caption("Data Source: Yahoo Finance | 분석 엔진: Linear Regression & Fibonacci Retracement")
