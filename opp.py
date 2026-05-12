import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="K-Stock Terminal", layout="wide")

# 2. 전종목 리스트 로드 (코스피/코스닥/코넥스 포함)
@st.cache_data
def get_all_korean_stocks():
    try:
        # FinanceDataReader의 KRX 종목 리스트 소스 활용
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        # 종목명: (코드, 시장구분) 형태의 딕셔너리 생성
        # Market 컬럼을 활용해 .KS(코스피)와 .KQ(코스닥/코넥스 등) 구분
        stock_map = {}
        for _, row in df.iterrows():
            code = str(row['Symbol']).zfill(6)
            market = str(row['Market'])
            
            # yfinance용 접미사 결정
            if market == 'KOSPI':
                suffix = '.KS'
            else:
                suffix = '.KQ'
                
            stock_map[row['Name']] = f"{code}{suffix}"
        return stock_map
    except Exception as e:
        st.error(f"종목 리스트 로드 중 오류 발생: {e}")
        return {"삼성전자": "005930.KS", "셀트리온": "068270.KS", "에코프로": "086520.KQ"}

stock_dict = get_all_korean_stocks()

# 3. 사이드바 검색 로직
with st.sidebar:
    st.header("🇰🇷 한국 주식 검색")
    search_input = st.text_input("종목명 입력 (예: 셀트리온, 삼성전자, 에코프로)", value="셀트리온")
    
    # 입력어가 포함된 모든 종목 나열
    matches = [name for name in stock_dict.keys() if search_input.upper() in name.upper()]
    
    if matches:
        # 검색 결과가 많을 수 있으므로 선택박스 제공
        selected_name = st.selectbox(f"검색 결과 ({len(matches)}건)", matches)
        target_ticker = stock_dict[selected_name]
    else:
        st.error("검색 결과가 없습니다.")
        target_ticker = None

    period = st.selectbox("조회 기간", ["6mo", "1y", "2y", "5y"], index=0)

# 4. 메인 화면: 데이터 로드 및 시각화
if target_ticker:
    # 데이터 다운로드
    data = yf.download(target_ticker, period=period, interval="1d", auto_adjust=True)
    
    if not data.empty:
        # Multi-Index 방어 (yfinance 최신 버전 대응)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        data = data.reset_index()
        
        # 간단한 지표 계산
        data['MA20'] = data['Close'].rolling(20).mean()
        curr_p = float(data['Close'].iloc[-1])
        prev_p = float(data['Close'].iloc[-2])
        change_pc = ((curr_p / prev_p) - 1) * 100

        st.title(f"📊 {selected_name} ({target_ticker})")
        
        col1, col2 = st.columns(2)
        col1.metric("현재가", f"{curr_p:,.0f}원", f"{change_pc:+.2f}%")
        col2.write(f"**시장 구분:** {'코스피' if '.KS' in target_ticker else '코스닥/기타'}")

        # 차트 생성
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, row_heights=[0.7, 0.3])

        # 캔들스틱
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], 
                                     low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        # 20일 이동평균선
        fig.add_trace(go.Scatter(x=data['Date'], y=data['MA20'], name="20일선", 
                                 line=dict(color='orange', width=1.5)), row=1, col=1)

        # 거래량
        colors = ['red' if r['Open'] < r['Close'] else 'blue' for _, r in data.iterrows()]
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], marker_color=colors, name="거래량"), row=2, col=1)

        fig.update_layout(template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"{selected_name} 데이터를 가져올 수 없습니다. (상장 폐지 혹은 티커 오류)")
