import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="Samsung Stock Scanner", layout="wide")

# 2. 한국 거래소 전체 종목 데이터 로드 (캐싱 처리)
@st.cache_data
def get_krx_list():
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        # 종목명과 티커만 추출하여 딕셔너리화 (005930 -> 005930.KS)
        return {row['Name']: f"{str(row['Symbol']).zfill(6)}.KS" for _, row in df.iterrows()}
    except:
        return {"삼성전자": "005930.KS", "삼성SDI": "006400.KS", "삼성물산": "028260.KS"}

stock_dict = get_krx_list()

# 3. 사이드바 검색 엔진 (사용자 요청 핵심 기능)
with st.sidebar:
    st.header("🔍 종목 검색")
    search_term = st.text_input("종목명을 입력하세요 (예: 삼성)", value="삼성")
    
    # "삼성"이 포함된 모든 종목 리스트 추출
    matched_names = [name for name in stock_dict.keys() if search_term in name]
    
    if matched_names:
        # 검색된 결과가 있을 경우 선택박스로 표시
        selected_stock = st.selectbox(f"'{search_term}' 검색 결과 ({len(matched_names)}개)", matched_names)
        target_ticker = stock_dict[selected_stock]
    else:
        st.error("검색 결과가 없습니다.")
        target_ticker = None

# 4. 메인 화면: 선택된 종목 분석
if target_ticker:
    try:
        # 데이터 가져오기 (코스피 시도 후 없으면 코스닥 시도)
        df = yf.download(target_ticker, period="1y", interval="1d", auto_adjust=True)
        if df.empty:
            df = yf.download(target_ticker.replace(".KS", ".KQ"), period="1y", interval="1d", auto_adjust=True)
            
        if not df.empty:
            # 멀티인덱스 처리
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()

            # 데이터 계산
            curr_p = df['Close'].iloc[-1]
            high_p = df['High'].max()
            low_p = df['Low'].min()

            # 📋 상단 대시보드
            st.title(f"📊 {selected_stock} 분석")
            c1, c2, c3 = st.columns(3)
            c1.metric("현재 가격", f"{curr_p:,.0f}원")
            c2.metric("최고가 (매도 목표)", f"{high_p:,.0f}원", f"{((high_p/curr_p)-1)*100:.1f}%")
            c3.metric("최저가 (매수 지지)", f"{low_p:,.0f}원", f"{((low_p/curr_p)-1)*100:.1f}%", delta_color="normal")

            # 차트
            fig = go.Figure(data=[go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
            fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error("데이터를 불러오는 중 오류가 발생했습니다.")
