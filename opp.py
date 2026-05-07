import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 기본 설정 및 한글 데이터 로딩
st.set_page_config(page_title="Technical Alpha V4.5", layout="wide")

@st.cache_data
def get_stock_master():
    try:
        # 주 경로: KRX 공식 리스트
        url = 'https://kind.krx.co.kr/corpofficial/corpList.do?method=download'
        df = pd.read_html(url, header=0)[0][['회사명', '종목코드']]
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        return df
    except:
        try:
            # 백업 경로: GitHub 데이터 (서버 장애 대비)
            backup_url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
            df_b = pd.read_csv(backup_url)
            return df_b[['Name', 'Symbol']].rename(columns={'Name':'회사명', 'Symbol':'종목코드'})
        except:
            return pd.DataFrame(columns=['회사명', '종목코드'])

master_df = get_stock_master()

# 2. 사이드바 - 사용자 입력
with st.sidebar:
    st.header("🔍 분석 설정")
    user_input = st.text_input("종목명(한글) 또는 티커 입력", value="삼성전자").strip()
    
    # 한글 -> 코드 변환 로직
    ticker = user_input.upper()
    if not user_input.isdigit() and not any(ext in ticker for ext in ['.KS', '.KQ']):
        match = master_df[master_df['회사명'] == user_input]
        if not match.empty:
            code = match['종목코드'].values[0]
            ticker = f"{code}.KS"
            st.success(f"🇰🇷 한국 종목 감지: {code}")
        else:
            st.info("💡 한글명을 찾지 못했습니다. 미국 티커로 시도합니다.")
    elif user_input.isdigit():
        ticker = f"{user_input}.KS"

    period_map = {"6개월": "6mo", "1년": "1y", "2년": "2y", "5년": "5y"}
    selected_p = st.selectbox("분석 기간", list(period_map.keys()), index=1)
    st.divider()
    st.caption("비스타릿 왕영준 대리님 전용 툴 v4.5")

# 3. 계산 함수 (회귀 채널)
def get_regression_channel(df):
    y = df['Close'].values
    x = np.arange(len(y))
    slope, intercept, _, _, _ = linregress(x, y)
    base = slope * x + intercept
    std = np.std(y - base)
    return base, base + (std * 2), base - (std * 2)

# 4. 메인 분석 및 차트
if ticker:
    try:
        data = yf.download(ticker, period=period_map[selected_p], auto_adjust=True)
        
        # 코스피/코스닥 스위칭
        if data.empty and ".KS" in ticker:
            ticker = ticker.replace(".KS", ".KQ")
            data = yf.download(ticker, period=period_map[selected_p], auto_adjust=True)

        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            
            # 수치 데이터
            curr_p = float(data['Close'].iloc[-1])
            high_p = float(data['High'].max())
            low_p = float(data['Low'].min())
            
            # 차트 구성
            fig = go.Figure()
            # 캔들스틱
            fig.add_trace(go.Candlestick(x=data['Date'], open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'], name="주가"))
            
            # 회귀 채널 (점선)
            base, upper, lower = get_regression_channel(data)
            fig.add_trace(go.Scatter(x=data['Date'], y=upper, name="채널상단(저항)", line=dict(color='rgba(255,100,100,0.5)', dash='dash')))
            fig.add_trace(go.Scatter(x=data['Date'], y=lower, name="채널하단(지지)", line=dict(color='rgba(100,255,100,0.5)', dash='dash')))
            
            # 피보나치 수평선 (일직선 보정)
            diff = high_p - low_p
            ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
            for r in ratios:
                line_y = high_p - (r * diff)
                fig.add_hline(y=line_y, line_dash="dot", line_color="gray", opacity=0.5,
                             annotation_text=f"Fib {r*100}%", annotation_position="bottom right")

            fig.update_layout(title=f"<b>{user_input} ({ticker})</b> 기술적 분석", template="plotly_dark", height=650, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
            # 5. 하단 전략 가이드 섹션
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("현재가", f"{curr_p:,.0f}")
                if curr_p <= lower[-1] * 1.02:
                    st.success("🎯 매수 적기: 지지선 근접")
                elif curr_p >= upper[-1] * 0.98:
                    st.warning("⚠️ 매도 고려: 저항선 근접")
            
            with col2:
                st.metric("목표가 (채널상단)", f"{upper[-1]:,.0f}")
                st.write(f"최고가: {high_p:,.0f}")
            
            with col3:
                st.metric("손절가 (채널하단)", f"{lower[-1]:,.0f}")
                st.write(f"최저가: {low_p:,.0f}")
        else:
            st.error("데이터를 불러오지 못했습니다. 종목명을 다시 확인해주세요.")
    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")
