import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="영준의 주식 분석 툴", layout="wide")

st.title("📊 실시간 주식 기술적 분석 툴")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 설정")
    ticker = st.text_input("티커 입력 (예: VOO, KORU, TSLA)", value="VOO").upper()
    # 기간 선택을 슬라이더 대신 선택 상자로 변경 (안정성)
    period = st.selectbox("분석 기간 선택", ["1mo", "3mo", "6mo", "1y", "2y"], index=3)

if ticker:
    try:
        # 데이터 호출 (더 안정적인 period 방식 사용)
        df = yf.download(ticker, period=period)
        
        if df.empty:
            st.error("데이터를 불러올 수 없습니다. 티커명을 확인하세요.")
        else:
            # 데이터 인덱스를 깔끔하게 정리
            df.index = pd.to_datetime(df.index)
            
            # 값 추출 (.item() 대신 values[0] 사용으로 더 안정적으로 추출)
            high_price = float(df['High'].max())
            low_price = float(df['Low'].min())
            diff = high_price - low_price
            current_price = float(df['Close'].iloc[-1])
            
            # 차트 생성
            fig = go.Figure()

            # 캔들스틱 차트
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name="Price"
            ))

            # 피보나치 라인 계산 (23.6%, 38.2%, 50%, 61.8%, 78.6%)
            levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
            level_names = ["0%", "23.6%", "38.2%", "50.0%", "61.8%", "78.6%", "100%"]
            colors = ["#7f7f7f", "#d62728", "#ff7f0e", "#2ca02c", "#1f77b4", "#9467bd", "#7f7f7f"]
            
            for level, name, color in zip(levels, level_names, colors):
                price = high_price - (level * diff)
                fig.add_hline(y=price, line_dash="dash", line_color=color,
                             annotation_text=f"{name} ({price:.2f})", 
                             annotation_position="bottom right")

            # 레이아웃 수정 (다크모드에서도 잘 보이도록)
            fig.update_layout(
                title=f"{ticker} 기술적 분석",
                yaxis_title="Price (USD)",
                xaxis_rangeslider_visible=False, # 하단 슬라이더 제거하여 차트를 더 크게
                height=700,
                template="plotly_dark"
            )
            
            st.plotly_chart(fig, use_container_width=True)

            # 지표 요약
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("현재가", f"${current_price:.2f}")
            with col2:
                st.metric("기간 내 최고가", f"${high_price:.2f}")
            with col3:
                st.metric("기간 내 최저가", f"${low_price:.2f}")

    except Exception as e:
        st.error(f"오류 발생: {e}")
