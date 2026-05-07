import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 페이지 설정
st.set_page_config(page_title="Technical Alpha V4.0", layout="wide")

# 1. 한글 종목명 -> 코드 변환용 마스터 데이터 로드 (KRX)
@st.cache_data
def load_krx_data():
    try:
        url = 'https://kind.krx.co.kr/corpofficial/corpList.do?method=download'
        df = pd.read_html(url, header=0)[0]
        df = df[['회사명', '종목코드']]
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        return df
    except:
        return pd.DataFrame(columns=['회사명', '종목코드'])

krx_list = load_krx_data()

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 트레이딩 터미널")
    user_input = st.text_input("종목명 또는 티커 입력", value="삼성전자").strip()
    
    # 종목 판별 로직
    ticker = user_input.upper()
    if not user_input.isdigit() and not any(ext in ticker for ext in ['.KS', '.KQ']):
        # 한글 이름 검색 시도
        match = krx_list[krx_list['회사명'] == user_input]
        if not match.empty:
            ticker = f"{match['종목코드'].values[0]}.KS" # 기본 KOSPI
            st.success(f"🇰🇷 한국 주식 확인: {user_input} ({ticker})")
        else:
            # 미국 주식으로 간주 (TSLA 등)
            ticker = user_input.upper()
    elif user_input.isdigit():
        ticker = f"{user_input}.KS"

    period = st.selectbox("분석 기간", ["6mo", "1y", "2y", "5y"], index=1)
    st.divider()
    show_guide = st.checkbox("매수/손절 가이드 표시", value=True)

# 2. 선형 회귀 채널 계산 함수
def calculate_channel(df):
    y = df['Close'].values
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std_dev = np.std(y - base)
    return base, base + (std_dev * 2), base - (std_dev * 2)

# 메인 분석 로직
if ticker:
    try:
        # 데이터 호출
        df = yf.download(ticker, period=period, auto_adjust=True)
        
        # 코스피 실패 시 코스닥 재시도
        if df.empty and ".KS" in ticker:
            ticker = ticker.replace(".KS", ".KQ")
            df = yf.download(ticker, period=period, auto_adjust=True)

        if not df.empty:
            # 데이터 구조 단순화
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            
            # 수치 데이터 추출
            curr_p = float(df['Close'].iloc[-1])
            high_v = float(df['High'].max())
            low_v = float(df['Low'].min())
            
            # 차트 생성
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"))

            # 3. 회귀 채널 추가
            base, upper, lower = calculate_channel(df)
            fig.add_trace(go.Scatter(x=df['Date'], y=upper, name="저항선", line=dict(color='#f87171', width=1, dash='dash')))
            fig.add_trace(go.Scatter(x=df['Date'], y=lower, name="지지선", line=dict(color='#4ade80', width=1, dash='dash')))

            # 4. 정밀 수평 피보나치 보정
            diff = high_v - low_v
            # hline을 사용하여 물결 현상 원천 차단
            fib_ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
            fib_colors = ["#475569", "#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#475569"]
            
            for r, c in zip(fib_ratios, fib_colors):
                price_level = high_v - (r * diff)
                fig.add_hline(y=price_level, line_dash="dot", line_color=c, 
                             annotation_text=f"Fib {r*100}% ({price_level:,.0f})", 
                             annotation_position="bottom right")

            fig.update_layout(title=f"<b>{user_input}</b> ({ticker}) 전략적 분석", template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # 5. 매수/손절 가이드 UI
            if show_guide:
                st.subheader("🎯 실시간 전략 가이드")
                sup_p = lower[-1]
                res_p = upper[-1]
                stop_l = sup_p * 0.97 # 지지선 하단 3%
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("### [ 매수 가이드 ]")
                    if curr_p <= sup_p * 1.03:
                        st.success(f"**매수 적기!** 현재 지지선(${sup_p:,.0f}) 부근입니다.")
                    elif curr_p >= res_p * 0.95:
                        st.warning("**과열 구간!** 저항선 근처이므로 매수를 지양하세요.")
                    else:
                        st.info("**관망 구간:** 추세 중심에서 이동 중입니다.")
                
                with col2:
                    st.write("### [ 리스크 관리 ]")
                    st.error(f"**강력 손절가: ${stop_l:,.0f}**")
                    st.info(f"**수익 목표가: ${res_p:,.0f}**")
                
                with col3:
                    st.write("### [ 주요 레벨 ]")
                    st.write(f"- 기간 최고점: {high_v:,.0f}")
                    st.write(f"- 기간 최저점: {low_v:,.0f}")
                    st.write(f"- 현재 가격: **{curr_p:,.0f}**")

        else:
            st.error("종목을 찾을 수 없습니다. 한글 이름이나 코드를 확인해 주세요.")
    except Exception as e:
        st.error(f"분석 엔진 오류: {e}")

### ✅ 최종 체크리스트
1.  **`requirements.txt` 확인:** `lxml` 한 줄이 꼭 추가되어야 한글 검색이 됩니다.
2.  **피보나치 선:** 이제 차트 오른쪽 구석에 깔끔하게 라벨이 붙은 **완벽한 수평선**으로 나옵니다.
3.  **한글 검색:** 이제 "삼성전자"라고 치시면 자동으로 `005930.KS`를 가져옵니다.

영준님의 주식 앱이 이제 시중의 유료 분석 툴 못지않게 강력해졌습니다! 바로 적용해 보시고, 또 필요한 게 생기면 말씀해 주세요._
