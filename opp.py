import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="Global Multi-Strategy Terminal", layout="wide")

# 2. 한국 주식 전종목 리스트 로딩 (정확도 우선)
@st.cache_data(show_spinner="전종목 데이터를 정확하게 동기화 중...")
def get_full_krx_list():
    try:
        # 한국거래소 전종목 리스트 소스
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        # 필요한 컬럼만 추출 (종목코드, 종목명, 시장구분)
        return df[['Symbol', 'Name', 'Market']]
    except Exception as e:
        st.error(f"데이터 로딩 실패: {e}")
        return pd.DataFrame(columns=['Symbol', 'Name', 'Market'])

krx_full_df = get_full_krx_list()

# 3. 사이드바 구성: 검색 효율성 극대화
with st.sidebar:
    st.header("🔍 국/내외 종목 통합 검색")
    
    # [검색어 입력]
    search_input = st.text_input("검색어 입력 (예: 삼성, 에코, NVDA)", value="삼성")
    
    # [한국 주식 필터링] - '삼성'이 들어간 모든 종목 추출
    kr_matches = krx_full_df[krx_full_df['Name'].str.contains(search_input, na=False, case=False)]
    
    # [결과 노출 방식]
    if not kr_matches.empty:
        st.success(f"국내주식 '{search_input}' 검색 결과: {len(kr_matches)}건")
        
        # 1. 사용자가 보고 고를 수 있는 선택박스 (이게 핵심)
        # 종목명과 코드를 합쳐서 보여줌
        kr_matches['Display'] = kr_matches['Name'] + " (" + kr_matches['Symbol'] + ")"
        selected_display = st.selectbox("분석할 국내 종목 선택", kr_matches['Display'].tolist())
        
        # 선택된 종목의 정보 추출
        selected_row = kr_matches[kr_matches['Display'] == selected_display].iloc[0]
        selected_name = selected_row['Name']
        selected_symbol = selected_row['Symbol']
        selected_market = selected_row['Market']
        
        # 티커 변환 (.KS 또는 .KQ)
        suffix = ".KS" if selected_market == 'KOSPI' else ".KQ"
        final_ticker = f"{selected_symbol}{suffix}"
        
        # 2. 코드 복사용 표 (요청하신 기능)
        with st.expander("전체 검색 결과 코드 보기"):
            st.dataframe(kr_matches[['Name', 'Symbol', 'Market']], hide_index=True)
            
    else:
        # 한국 주식이 아니면 미국 티커로 간주
        st.info("국내 검색 결과 없음 -> 해외 티커 모드로 전환")
        final_ticker = search_input.upper()
        selected_name = search_input.upper()

    st.divider()
    
    # [기존 기능: 추천 스캐너 및 기간 설정]
    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=1)
    st.subheader("🛠️ 시각화 옵션")
    show_fib = st.checkbox("피보나치 황금선 표시", value=True)
    show_buy = st.checkbox("★BUY 타점 표시", value=True)

# 4. 차트 및 전략 엔진 (기존 로직 유지)
def add_strategy(df):
    if len(df) < 20: return df
    # 이평선 및 RSI
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    delta = df['Close'].diff()
    df['RSI'] = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean())))
    # 피보나치 61.8%
    hp, lp = df['High'].max(), df['Low'].min()
    df['Fib_618'] = hp - 0.618 * (hp - lp)
    # 타점 (골든크로스 or 과매도)
    df['Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 5. 메인 화면 출력
if final_ticker:
    data = yf.download(final_ticker, period=period, interval="1d", auto_adjust=True)
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_strategy(data)
        
        st.title(f"📊 {selected_name} ({final_ticker}) 전략 리포트")
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])
        
        # 캔들스틱
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        # 피보나치 황금선
        if show_fib and 'Fib_618' in data.columns:
            val = data['Fib_618'].iloc[-1]
            fig.add_trace(go.Scatter(x=data['Date'], y=[val]*len(data), name="황금지지(61.8%)", line=dict(color='gold', width=3, dash='dash')), row=1, col=1)
            
        # ★BUY 타점
        if show_buy and 'Signal' in data.columns:
            buys = data[data['Signal']]
            fig.add_trace(go.Scatter(x=buys['Date'], y=buys['Low']*0.98, mode='markers+text', text=["★BUY"]*len(buys), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='매수타점'), row=1, col=1)
            
        # 거래량
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='gray'), row=2, col=1)
        
        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(f"'{final_ticker}' 데이터를 찾을 수 없습니다. 티커나 코드를 정확히 확인해 주세요.")
