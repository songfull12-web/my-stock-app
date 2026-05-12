import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="KRX Strategy Terminal", layout="wide")

# 2. 한국 주식 전종목 리스트 로드 (최대한 많은 소스 확보)
@st.cache_data(show_spinner="전종목 데이터를 불러오는 중...")
def get_krx_list():
    try:
        # 주요 소스: FinanceDataReader 방식의 GitHub 데이터
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Symbol', 'Name', 'Market']]
    except:
        # 로드 실패 시에도 검색이 가능하도록 최소 데이터 유지
        return pd.DataFrame([
            {"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"},
            {"Symbol": "000660", "Name": "SK하이닉스", "Market": "KOSPI"},
            {"Symbol": "068270", "Name": "셀트리온", "Market": "KOSPI"},
            {"Symbol": "247540", "Name": "에코프로비엠", "Market": "KOSDAQ"}
        ])

krx_df = get_krx_list()

# 3. 사이드바: 검색 및 코드 확인용 칸 추가
with st.sidebar:
    st.header("🔍 1단계: 종목/코드 찾기")
    search_keyword = st.text_input("종목명 입력 (예: 삼성, 에코, 카카오)", value="삼성")
    
    # [핵심] 검색어 포함된 모든 종목 리스트 출력
    filtered_df = krx_df[krx_df['Name'].str.contains(search_keyword, na=False)].copy()
    
    if not filtered_df.empty:
        st.write(f"✅ '{search_keyword}' 검색 결과 ({len(filtered_df)}건)")
        # 사용자가 코드를 바로 볼 수 있도록 표로 출력
        st.dataframe(filtered_df[['Name', 'Symbol', 'Market']], hide_index=True, height=250)
        st.caption("위 표에서 분석할 종목의 'Symbol'을 확인하세요.")
    else:
        st.error("검색 결과가 없습니다.")

    st.divider()
    
    st.header("📊 2단계: 분석 실행")
    # [핵심] 사용자가 코드를 직접 입력하는 칸
    target_code = st.text_input("분석할 종목코드 입력 (6자리)", value="005930")
    market_type = st.radio("시장 선택", ["코스피(KS)", "코스닥(KQ)"], horizontal=True)
    
    suffix = ".KS" if "코스피" in market_type else ".KQ"
    final_ticker = f"{target_code.strip()}{suffix}"
    
    st.info(f"현재 분석 타겟: {final_ticker}")

# 4. 차트 분석 로직 (피보나치, ★BUY 타점 유지)
def add_indicators(df):
    if len(df) < 20: return df
    # 이평선
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    # 피보나치
    hp, lp = df['High'].max(), df['Low'].min()
    diff = hp - lp
    df['Fib_618'] = hp - 0.618 * diff
    df['Fib_382'] = hp - 0.382 * diff
    # 매수 신호
    df['Buy_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)) | (df['RSI'] < 30)
    return df

# 5. 메인 화면 출력
if final_ticker:
    data = yf.download(final_ticker, period="1y", interval="1d", auto_adjust=True)
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = add_indicators(data)
        
        st.title(f"📈 {final_ticker} 전략 스캐너")
        
        # 차트 그리기
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
        
        # 캔들스틱
        fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)
        
        # 황금선 (61.8%) 표시
        if 'Fib_618' in data.columns:
            f618 = data['Fib_618'].iloc[-1]
            fig.add_trace(go.Scatter(x=data['Date'], y=[f618]*len(data), name="황금지지선", line=dict(color='gold', width=3, dash='dash')), row=1, col=1)
            
        # ★BUY 타점
        buy_pts = data[data['Buy_Signal']]
        fig.add_trace(go.Scatter(x=buy_pts['Date'], y=buy_pts['Low']*0.97, mode='markers+text', text=["★BUY"]*len(buy_pts), textposition="bottom center", marker=dict(symbol='star', size=12, color='lime'), name='매수타점'), row=1, col=1)
        
        # 거래량
        fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], name="거래량", marker_color='gray'), row=2, col=1)
        
        fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("데이터를 불러오지 못했습니다. 종목 코드와 시장(KS/KQ)을 다시 확인해 주세요.")
