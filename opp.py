import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 페이지 설정
st.set_page_config(page_title="Stock Terminal", layout="wide")

# [핵심] 1. 구매하기 좋은 조건의 주식 스캐너 (예시 종목군 분석)
def get_recommendations():
    # 분석할 주요 종목 리스트
    target_stocks = {
        "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "LG에너지솔루션": "373220.KS",
        "삼성바이오로직스": "207940.KS", "현대차": "005380.KS", "NAVER": "035420.KS",
        "카카오": "035720.KS", "삼성SDI": "006400.KS", "기아": "000270.KS"
    }
    
    recom_list = []
    for name, ticker in target_stocks.items():
        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty: continue
            
            # 기술적 지표 계산
            close = df['Close'].iloc[-1]
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            
            # RSI 계산
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            
            # 매수 조건 설정: RSI 35 미만(저평가) 혹은 20일선 돌파
            if rsi < 40:
                recom_list.append({"종목": name, "티커": ticker, "이유": "과매도 구간(저평가)", "RSI": round(rsi, 1)})
            elif close > ma20:
                recom_list.append({"종목": name, "티커": ticker, "이유": "상승 추세 전환", "RSI": round(rsi, 1)})
        except:
            continue
    return pd.DataFrame(recom_list)

# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    # 검색 대신 직접 입력 (가장 확실함)
    ticker_input = st.text_input("종목 코드 입력 (예: 005930)", value="005930")
    if not ticker_input.endswith((".KS", ".KQ")):
        ticker_input += ".KS" # 기본 코스피 설정
    
    st.divider()
    if st.button("🚀 매수 추천 종목 찾기"):
        recom_df = get_recommendations()
        st.write(recom_df)

# 메인 화면
st.title("📈 주식 분석 및 추천 터미널")

try:
    # 데이터 불러오기
    data = yf.download(ticker_input, period="1y", interval="1d", auto_adjust=True)
    
    if not data.empty:
        # 데이터 정리
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        
        # 지표 계산
        curr_p = data['Close'].iloc[-1]
        high_v = data['High'].max()
        low_v = data['Low'].min()
        
        # 상단 대시보드 (매수/매도 가격 포함)
        c1, c2, c3 = st.columns(3)
        c1.metric("현재가", f"{curr_p:,.0f}")
        c2.metric("매수 적정가 (전저점 부근)", f"{low_v:,.0f}")
        c3.metric("매도 목표가 (전고점 부근)", f"{high_v:,.0f}")
        
        st.divider()
        
        # 차트 시각화
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], 
                                   low=data['Low'], close=data['Close'], name="주가"))
        fig.update_layout(template="plotly_dark", height=600)
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.warning("데이터를 불러올 수 없습니다. 종목 코드를 다시 확인해 주세요.")

except Exception as e:
    st.error(f"오류가 발생했습니다: {e}")
