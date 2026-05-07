import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="영준의 주식 분석 툴", layout="wide")

st.title("📊 실시간 주식 기술적 분석 툴")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 설정")
    ticker = st.text_input("티커 입력 (예: VOO, KORU, TSLA)", value="VOO").upper()
    days = st.slider("분석 기간 (일)", 30, 730, 365)

# 데이터 가져오기
end_date = datetime.now()
start_date = end_date - timedelta(days=days)

if ticker:
    try:
        df = yf.download(ticker, start=start_date, end=end_date)
        
        if df.empty:
            st.error("데이터를 불러올 수 없습니다. 티커명을 확인하세요.")
        else:
            # 피보나치 계산
            high_price = df['High'].max()
            low_price = df['Low'].min()
            diff = high_price - low_price
            
            # 차트 생성
            fig = go.Figure()

            # 캔들스틱 차트
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name="Price"
            ))

            # 피보나치 라인
            levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
            colors = ["gray", "red", "orange", "green", "blue", "purple", "gray"]
            
            for level, color in zip(levels, colors):
                price = high_price - (level * diff)
                fig.add_hline(y=float(price), line_dash="dot", line_color=color,
                             annotation_text=f"{level*100}% ({price:.2f})", 
                             annotation_position="bottom right")

            fig.update_layout(title=f"{ticker} 기술적 분석 (피보나치)", yaxis_title="Price (USD)", height=800)
            st.plotly_chart(fig, use_container_width=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("현재가", f"${df['Close'].iloc[-1]:.2f}")
            with col2:
                st.metric("기간 고점", f"${high_price:.2f}")
            with col3:
                st.metric("기간 저점", f"${low_price:.2f}")

    except Exception as e:
        st.error(f"오류 발생: {e}")
