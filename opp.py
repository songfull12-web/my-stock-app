import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Technical Analysis Tool", layout="wide")

# 2. 한글 종목명 마스터 데이터 로드 (강력한 백업 로직)
@st.cache_data
def load_stock_master():
    try:
        # 경로 1: KRX 공식 다운로드
        url = 'https://kind.krx.co.kr/corpofficial/corpList.do?method=download'
        df = pd.read_html(url, header=0)[0][['회사명', '종목코드']]
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        return df
    except:
        try:
            # 경로 2: 대체 GitHub 데이터
            url_bak = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
            df_bak = pd.read_csv(url_bak)
            return df_bak[['Name', 'Symbol']].rename(columns={'Name':'회사명', 'Symbol':'종목코드'})
        except:
            return pd.DataFrame(columns=['회사명', '종목코드'])

master_df = load_stock_master()

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 설정")
    user_input = st.text_input("종목명(한글) 또는 티커", value="삼성전자").strip()
    
    # 한글 검색 처리
    ticker = user_input.upper()
    if not user_input.isdigit() and not any(ext in ticker for ext in ['.KS', '.KQ']):
        match = master_df[master_df['회사명'] == user_input]
        if not match.empty:
            ticker = f"{match['종목코드'].values[0]}.KS"
            st.success(f"🇰🇷 확인: {ticker}")
        else:
            st.info("💡 미국 주식 티커로 분석합니다.")

    period_map = {"6개월": "6mo", "1년": "1y", "2년": "2y", "5년": "5y"}
    selected_p = st.selectbox("분석 기간", list(period_map.keys()), index=1)
    
    st.divider()
    # 체크박스 옵션 추가
    show_channel = st.checkbox("회귀 채널(추세선) 표시", value=True)
    show_fib = st.checkbox("피보나치 수평선 표시", value=True)

# 4. 분석 계산 함수
def get_analysis(df):
    y = df['Close'].values
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    line = slope * x + intercept
    std = np.std(y - line)
    return line, line + (std * 2), line - (std * 2)

# 5. 메인 차트 및 가이드
if ticker:
    try:
        data = yf.download(ticker, period=period_map[selected_p], auto_adjust=True)
        if data.empty and ".KS" in ticker:
            ticker = ticker.replace(".KS", ".KQ")
            data = yf.download(ticker, period=period_map[selected_p], auto_adjust=True)

        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            
            curr_p = float(data['Close'].iloc[-1])
            high_p, low_p = float(data['High'].max()), float(data['Low'].min())
            
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"))

            # 회귀 채널 표시 여부
            if show_channel:
                base, upper, lower = get_analysis(data)
                fig.add_trace(go.Scatter(x=data['Date'], y=upper, name="저항선", line=dict(color='rgba(255,100,100,0.5)', dash='dash')))
                fig.add_trace(go.Scatter(x=data['Date'], y=lower, name="지지선", line=dict(color='rgba(100,255,100,0.5)', dash='dash')))
            
            # 피보나치 표시 여부 (일직선 보정)
            if show_fib:
                diff = high_p - low_p
                for r in [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]:
                    val = high_p - (r * diff)
                    fig.add_hline(y=val, line_dash="dot", line_color="gray", opacity=0.3, 
                                 annotation_text=f"Fib {r*100}%", annotation_position="bottom right")

            fig.update_layout(title=f"<b>{user_input} ({ticker})</b> 분석", template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 가이드 섹션
            st.divider()
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("현재가", f"{curr_p:,.0f}")
            with c2:
                st.metric("기간 고점", f"{high_p:,.0f}")
            with c3:
                st.metric("기간 저점", f"{low_p:,.0f}")
        else:
            st.error("데이터를 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"오류: {e}")
