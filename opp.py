import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from scipy.stats import linregress

# 1. 페이지 설정
st.set_page_config(page_title="Professional Stock Terminal", layout="wide")

# 2. 종목 데이터 로드
@st.cache_data
def get_stock_dict():
    stocks = {"삼성전자": "005930", "SK하이닉스": "000660", "현대차": "005380", "NAVER": "035420", "카카오": "035720"}
    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        for _, row in df.iterrows():
            stocks[str(row['Name'])] = str(row['Symbol']).zfill(6)
    except:
        pass
    return stocks

stock_dict = get_stock_dict()

# 3. 분석 계산 함수 (피보나치, 거래량, 정교한 매수 타점)
def add_indicators(df):
    if len(df) < 20: return df
    
    # 이평선
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 피보나치 채널 (최근 고점/저점 기준)
    high_p, low_p = df['High'].max(), df['Low'].min()
    diff = high_p - low_p
    df['Fib_0'] = high_p
    df['Fib_236'] = high_p - 0.236 * diff
    df['Fib_382'] = high_p - 0.382 * diff
    df['Fib_500'] = high_p - 0.5 * diff
    df['Fib_618'] = high_p - 0.618 * diff
    df['Fib_100'] = low_p

    # --- 매수 타점 로직 ---
    # 1. RSI가 35 이하인 경우 (과매도)
    # 2. 주가가 피보나치 61.8% 지지선에 닿고 반등할 때
    # 3. 20일선이 60일선을 돌파할 때 (골든크로스)
    df['Buy_Signal'] = (
        (df['RSI'] < 35) | 
        ((df['Close'] > df['Fib_618']) & (df['Low'] <= df['Fib_618'])) |
        ((df['MA20'] > df['MA60']) & (df['MA20'].shift(1) <= df['MA60'].shift(1)))
    )
    
    # 매도 신호 (RSI 과열 혹은 데드크로스)
    df['Sell_Signal'] = (df['RSI'] > 65) | ((df['MA20'] < df['MA60']) & (df['MA20'].shift(1) >= df['MA60'].shift(1)))
    
    return df

# 4. 사이드바 설정
with st.sidebar:
    st.header("🔍 분석 엔진")
    search_input = st.text_input("종목명/티커 입력", value="삼성전자").strip()
    matches = [name for name in stock_dict.keys() if search_input in name]
    
    if matches:
        selected_name = st.selectbox(f"검색 결과", matches)
        code = stock_dict[selected_name]
        final_ticker = f"{code}.KS" if code.isdigit() else code
    else:
        final_ticker = search_input.upper()
        selected_name = search_input

    interval = st.selectbox("차트 주기", ["60m", "1d", "1wk"], index=1)
    period = st.selectbox("조회 기간", ["3mo", "6mo", "1y", "2y"], index=1)
    
    st.subheader("🛠️ 시각화 옵션")
    show_fib = st.checkbox("피보나치 채널 활성화", value=True)
    show_ma = st.checkbox("이동평균선", value=True)
    show_vol = st.checkbox("거래량 차트", value=True)
    show_rsi = st.checkbox("RSI 지표", value=True)

# 5. 메인 출력 영역
if final_ticker:
    try:
        data = yf.download(final_ticker, period=period, interval=interval, auto_adjust=True)
        if data.empty: st.error("데이터를 불러올 수 없습니다.")
        else:
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            data = data.reset_index()
            data = add_indicators(data)
            
            curr_p = float(data['Close'].iloc[-1])
            rsi_val = data['RSI'].iloc[-1]
            fib_618_val = data['Fib_618'].iloc[-1]

            st.title(f"📊 {selected_name} ({final_ticker})")
            
            # --- 매수 타점 미리 알림 ---
            if curr_p <= fib_618_val * 1.015 and curr_p >= fib_618_val * 0.985:
                st.success(f"🎯 **매수 타점 포착:** 현재 주가가 피보나치 황금 지지선(61.8%) 근처입니다!")
            elif rsi_val < 35:
                st.warning(f"⚠️ **과매도 상태:** RSI 지수가 낮아 반등 가능성이 높습니다.")

            # 차트 레이아웃 설정 (행 구성: 메인/피보나치 -> 거래량 -> RSI)
            row_list = [1]
            if show_vol: row_list.append(2)
            if show_rsi: row_list.append(3 if show_vol else 2)
            
            total_rows = len(row_list)
            row_heights = [0.6] + [0.2] * (total_rows - 1)

            fig = make_subplots(
                rows=total_rows, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=row_heights,
                specs=[[{"secondary_y": True}]] + [[{"secondary_y": False}]] * (total_rows - 1)
            )

            # 1. 메인 캔들스틱
            fig.add_trace(go.Candlestick(
                x=data.iloc[:,0], open=data['Open'], high=data['High'], 
                low=data['Low'], close=data['Close'], name="주가"
            ), row=1, col=1)

            # 2. 피보나치 채널 (시각화 개선)
            if show_fib:
                fib_colors = ['rgba(255, 0, 0, 0.15)', 'rgba(255, 165, 0, 0.15)', 'rgba(0, 255, 0, 0.15)', 'rgba(0, 0, 255, 0.15)']
                levels = [('Fib_0', 'Fib_236'), ('Fib_236', 'Fib_382'), ('Fib_382', 'Fib_500'), ('Fib_500', 'Fib_618')]
                for i, (start, end) in enumerate(levels):
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data[start], line=dict(width=0), showlegend=False, hoverinfo='skip'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data[end], fill='tonexty', fillcolor=fib_colors[i], line=dict(width=0.5, color='gray'), name=f"레벨 {i+1}"), row=1, col=1)
                # 61.8% 선 강조
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['Fib_618'], name="61.8% 황금선", line=dict(color='gold', width=2.5, dash='solid')), row=1, col=1)

            # 3. 매수/매도 타점 표시
            buy_pts = data[data['Buy_Signal']]
            fig.add_trace(go.Scatter(
                x=buy_pts.iloc[:,0], y=buy_pts['Low'] * 0.96, 
                mode='markers+text', text=["매수"]*len(buy_pts), textposition="bottom center",
                name='매수타점', marker=dict(symbol='triangle-up', size=14, color='#00FF00')
            ), row=1, col=1)

            if show_ma:
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['MA20'], name="20일선", line=dict(color='cyan', width=1.5)), row=1, col=1)

            # 4. 거래량 (Volume) - 두 번째 행
            if show_vol:
                vol_row = 2
                colors = ['red' if row['Open'] < row['Close'] else 'blue' for _, row in data.iterrows()]
                fig.add_trace(go.Bar(x=data.iloc[:,0], y=data['Volume'], name="거래량", marker_color=colors, opacity=0.7), row=vol_row, col=1)

            # 5. RSI - 세 번째 행
            if show_rsi:
                rsi_row = total_rows
                fig.add_trace(go.Scatter(x=data.iloc[:,0], y=data['RSI'], name="RSI", line=dict(color='#FFD700')), row=rsi_row, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=rsi_row, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=rsi_row, col=1)

            fig.update_layout(template="plotly_dark", height=900, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=50, b=50))
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")
