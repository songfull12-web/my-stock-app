import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Professional Stock Terminal", layout="wide")

# 2. 종목 데이터 로드 (KRX 전체 종목 리스트 가져오기)
@st.cache_data
def get_stock_dict():
    # 기본 종목 예시
    stocks = {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS"}
    try:
        # FinanceDataReader와 유사하게 KRX 종목 리스트를 GitHub에서 가져옴
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        # 검색 효율을 위해 {종목명: 티커} 딕셔너리로 변환
        for _, row in df.iterrows():
            stocks[row['Name']] = row['Symbol']
    except:
        pass
    return stocks

stock_dict = get_stock_dict()

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 엔진")
    # 검색어 입력
    search_input = st.text_input("종목명 검색 (예: 삼성, 현대)", value="삼성전자").strip()
    
    final_ticker = ""
    if search_input:
        # 입력한 단어가 포함된 모든 종목명 찾기
        matches = [name for name in stock_dict.keys() if search_input in name]
        
        if matches:
            # 검색 결과가 있으면 선택 박스 노출 (여기서 다른 삼성 시리즈 선택 가능)
            selected_name = st.selectbox(f"'{search_input}' 검색 결과 ({len(matches)}개)", matches)
            code = stock_dict[selected_name]
            # 한국 시장 포맷에 맞게 티커 수정 (.KS 또는 .KQ 자동 처리 로직은 다운로드 시 적용)
            final_ticker = f"{code}.KS" if code.isdigit() else code
        else:
            # 검색 결과가 없을 경우 사용자가 직접 티커 입력 가능 (예: AAPL, TSLA)
            st.warning("검색 결과가 없습니다. 직접 티커를 입력하세요.")
            final_ticker = search_input.upper()

    st.divider()
    interval = st.selectbox("차트 주기", ["60m", "1d", "1wk", "1mo"], index=1)
    period = st.selectbox("조회 기간", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
    
    st.subheader("🛠️ 지표 커스텀")
    show_ma = st.checkbox("이동평균선(MA)", value=True)
    show_trend = st.checkbox("추세 지지/저항선", value=True)
    show_signals = st.checkbox("매수/매도 타이밍 표시", value=True)
    show_vol = st.checkbox("거래량 차트", value=True)
    show_rsi = st.checkbox("RSI 지표", value=True)
    show_fib = st.checkbox("피보나치 구역", value=True)

# 4. 지표 및 신호 계산 함수
def add_indicators(df):
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 매수/매도 신호 로직
    df['Buy_Signal'] = (df['RSI'] < 35) | ((df['MA20'] > df['MA60']) & (df['MA20'].shift(1) <= df['MA60'].shift(1)))
    df['Sell_Signal'] = (df['RSI'] > 65) | ((df['MA20'] < df['MA60']) & (df['MA20'].shift(1) >= df['MA60'].shift(1)))
    return df

# 5. 메인 출력 영역
if final_ticker:
    try:
        # 데이터 다운로드 (코스피 우선 시도 후 실패 시 코스닥 시도)
        data = yf.download(final_ticker, period=period, interval=interval, auto_adjust=True)
        if data.empty and ".KS" in final_ticker:
            data = yf.download(final_ticker.replace(".KS", ".KQ"), period=period, interval=interval, auto_adjust=True)

        if not data.empty:
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            data = add_indicators(data)
            
            # 핵심 수치 추출
            curr_p = float(data['Close'].iloc[-1])
            high_v, low_v = float(data['High'].max()), float(data['Low'].min())
            rsi_val = data['RSI'].iloc[-1]

            # 📋 [1] 상단 핵심 대시보드
            st.title(f"📊 {selected_name if 'selected_name' in locals() else final_ticker} 분석 리포트")
            m_cols = st.columns(4)
            with m_cols[0]:
                st.metric("현재가", f"{curr_p:,.0f}")
            with m_cols[1]:
                st.metric("전고점 (목표)", f"{high_v:,.0f}", f"{((high_v/curr_p)-1)*100:.1f}%")
            with m_cols[2]:
                st.metric("전저점 (지지)", f"{low_v:,.0f}", f"{((low_v/curr_p)-1)*100:.1f}%", delta_color="normal")
            with m_cols[3]:
                rsi_status = "과매수" if rsi_val > 70 else "과매도" if rsi_val < 30 else "보통"
                st.metric("RSI 지수", f"{rsi_val:.1f}", rsi_status)

            st.divider()

            # [2] 차트 생성
            rows = 2 if show_rsi or show_vol else 1
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                               row_heights=[0.7, 0.3] if rows == 2 else [1.0],
                               specs=[[{"secondary_y": True}], [{"secondary_y": False}]] if rows == 2 else [[{"secondary_y": True}]])

            # 캔들차트
            fig.add_trace(go.Candlestick(x=data.iloc[:,0], open=data['Open'], high=data['High'], 
                                       low=data['Low'], close=data['Close'], name="주가"), row=1, col=1)

            # 매수/매도 타이밍 화살표
            if show_signals:
                buy_pts = data[data['Buy_Signal']]
                sell_pts = data[data['Sell_Signal']]
                fig.add_trace(go.Scatter(x=buy_pts.iloc[:,0], y=buy_pts['Low']*0.97, mode='markers', 
                                         name='매수 타이밍', marker=dict(symbol='triangle-up', size=12, color='#00FF00')), row=1, col=1)
                fig.add_trace(go.Scatter(x=sell_pts.iloc[:,0], y=sell_pts['High']*1.03, mode='markers', 
                                         name='매도 타이밍', marker=dict(symbol='triangle-down', size=12, color='#FF0000')), row=1, col=1)

            # 이평선
            if show_ma:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA20'], name="20일선", line=dict(color='cyan', width=1.5)), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA60'], name="60일선", line=dict(color='magenta', width=1.5)), row=1, col=1)

            # 지지/저항 추세선
            if show_trend:
                y_vals, x_vals = data['Close'].values, np.arange(len(data))
                slope, intercept, _, _, std_err = linregress(x_vals, y_vals)
                if slope > 0: # 상승추세 지지선
                    line = (intercept + slope * x_vals) - (std_err * 12)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=line, name="상승지지", line=dict(color='#00FF00', width=1.5, dash='dot')), row=1, col=1)
                else: # 하락추세 저항선
                    line = (intercept + slope * x_vals) + (std_err * 12)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=line, name="하락저항", line=dict(color='#FF0000', width=1.5, dash='dot')), row=1, col=1)

            # 피보나치 구역
            if show_fib:
                diff = high_v - low_v
                for r in [0, 0.382, 0.5, 0.618, 1.0]:
                    val = high_v - (r * diff)
                    fig.add_hline(y=val, line_dash="dash", line_color="rgba(255,255,255,0.15)", row=1, col=1)

            # 하단 보조지표 (거래량/RSI)
            if show_vol:
                v_cols = ['red' if r['Open'] < r['Close'] else 'blue' for _, r in data.iterrows()]
                fig.add_trace(go.Bar(x=data.iloc[:,0], y=data['Volume'], name="거래량", marker_color=v_cols, opacity=0.4), row=rows, col=1)
            if show_rsi:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#FFD700')), row=rows, col=1)

            fig.update_layout(template="plotly_dark", height=800, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

            # [3] 실시간 전략 가이드
            st.subheader("💡 투자 의견 요약")
            g_cols = st.columns(3)
            with g_cols[0]:
                if rsi_val < 30: st.success("🎯 **RSI 저평가**: 과매도 구간입니다. 분할 매수를 고려하세요.")
                elif rsi_val > 70: st.error("⚠️ **RSI 고평가**: 과매수 구간입니다. 익절을 고려하세요.")
                else: st.info("ℹ️ **심리 중립**: 현재 시장 심리는 안정적입니다.")
            with g_cols[1]:
                if data['MA20'].iloc[-1] > data['MA60'].iloc[-1]: st.success("📈 **정배열**: 추세가 살아있는 상승 구간입니다.")
                else: st.error("📉 **역배열**: 하락 압력이 강한 구간입니다. 주의하세요.")
            with g_cols[2]:
                mid_p = high_v - (0.5 * (high_v - low_v))
                if curr_p < mid_p: st.warning(f"📉 **가격 위치**: 기간 중심값({mid_p:,.0f}) 아래에 위치합니다.")
                else: st.info(f"📈 **가격 위치**: 기간 중심값({mid_p:,.0f}) 위에서 강세를 보입니다.")

        else: st.error("종목 데이터를 가져오지 못했습니다. 티커(종목코드)를 확인해주세요.")
    except Exception as e: st.error(f"오류가 발생했습니다: {e}")

st.caption("Data Source: Yahoo Finance & KRX | 본 리포트는 기술적 분석 기반으로 투자 판단의 책임은 사용자에게 있습니다.")
