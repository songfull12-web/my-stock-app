import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime

# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="Global Strategy Terminal",
    layout="wide"
)

# =========================================================
# 스타일
# =========================================================

st.markdown("""
<style>
.metric-card {
    background-color: #111;
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #333;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# KRX 마스터 DB
# =========================================================

@st.cache_data(show_spinner="KRX 종목 동기화 중...")
def load_krx_master_db():

    try:
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"

        df = pd.read_csv(url)

        return df[['Symbol', 'Name', 'Market']].dropna()

    except:

        return pd.DataFrame([
            {
                "Symbol": "005930",
                "Name": "삼성전자",
                "Market": "KOSPI"
            }
        ])

master_db = load_krx_master_db()

# =========================================================
# 데이터 로드
# =========================================================

@st.cache_data(ttl=300)
def fetch_data(ticker, period):

    try:

        data = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False
        )

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data = data.reset_index()

        return data

    except:
        return pd.DataFrame()

# =========================================================
# 지표 계산
# =========================================================

def calculate_indicators(df):

    if len(df) < 120:
        return df

    # -----------------------------
    # 이동평균선
    # -----------------------------

    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    df['MA120'] = df['Close'].rolling(120).mean()

    # -----------------------------
    # RSI
    # -----------------------------

    delta = df['Close'].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df['RSI'] = 100 - (100 / (1 + rs))

    # -----------------------------
    # MACD
    # -----------------------------

    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()

    df['MACD'] = ema12 - ema26
    df['MACD_SIGNAL'] = df['MACD'].ewm(span=9).mean()

    # -----------------------------
    # 거래량 평균
    # -----------------------------

    df['VOL_MA20'] = df['Volume'].rolling(20).mean()

    # -----------------------------
    # ATR
    # -----------------------------

    high_low = df['High'] - df['Low']

    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())

    ranges = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    )

    true_range = np.max(ranges, axis=1)

    df['ATR'] = true_range.rolling(14).mean()

    # =====================================================
    # 피보나치 계산
    # 최근 120봉 기준
    # =====================================================

    lookback = 120

    recent = df.tail(lookback)

    hp = recent['High'].max()
    lp = recent['Low'].min()

    diff = hp - lp

    df['Fib_0'] = hp
    df['Fib_236'] = hp - 0.236 * diff
    df['Fib_382'] = hp - 0.382 * diff
    df['Fib_500'] = hp - 0.500 * diff
    df['Fib_618'] = hp - 0.618 * diff
    df['Fib_786'] = hp - 0.786 * diff
    df['Fib_100'] = lp

    return df

# =========================================================
# 전략 엔진
# =========================================================

def generate_signals(df):

    if len(df) < 120:
        return df

    # =====================================================
    # BUY SIGNAL
    # =====================================================

    df['Buy_Signal'] = (

        (df['Close'] > df['MA20']) &

        (df['MA20'] > df['MA60']) &

        (df['RSI'] > 45) &
        (df['RSI'] < 65) &

        (df['MACD'] > df['MACD_SIGNAL']) &

        (df['Volume'] > df['VOL_MA20']) &

        (df['Close'] > df['Fib_618'])

    )

    # =====================================================
    # SELL SIGNAL
    # =====================================================

    df['Sell_Signal'] = (

        (df['RSI'] > 72) |

        (df['Close'] < df['MA20']) |

        (df['MACD'] < df['MACD_SIGNAL'])

    )

    return df

# =========================================================
# 점수 시스템
# =========================================================

def calculate_score(df):

    score = 0

    latest = df.iloc[-1]

    if latest['Close'] > latest['MA20']:
        score += 20

    if latest['MA20'] > latest['MA60']:
        score += 20

    if latest['MACD'] > latest['MACD_SIGNAL']:
        score += 20

    if 45 <= latest['RSI'] <= 65:
        score += 20

    if latest['Volume'] > latest['VOL_MA20']:
        score += 20

    return score

# =========================================================
# 추천 등급
# =========================================================

def recommendation_text(score):

    if score >= 80:
        return "🔥 강력매수"

    elif score >= 60:
        return "✅ 매수유망"

    elif score >= 40:
        return "⚠ 관망"

    else:
        return "❌ 비추천"

# =========================================================
# 사이드바
# =========================================================

with st.sidebar:

    st.title("🌍 Global Strategy Terminal")

    query = st.text_input(
        "종목 검색",
        value="삼성"
    )

    matches = master_db[
        master_db['Name'].str.contains(
            query,
            na=False,
            case=False
        )
    ]

    if not matches.empty:

        st.subheader(f"검색 결과 ({len(matches)})")

        st.dataframe(
            matches[['Name', 'Symbol', 'Market']],
            use_container_width=True,
            hide_index=True,
            height=300
        )

        options = [
            f"{r['Name']} ({r['Symbol']})"
            for _, r in matches.iterrows()
        ]

        selected = st.selectbox(
            "종목 선택",
            options
        )

        stock_code = selected.split("(")[1].replace(")", "")

        market = matches[
            matches['Symbol'] == stock_code
        ].iloc[0]['Market']

        ticker = f"{stock_code}.KS" if market == "KOSPI" else f"{stock_code}.KQ"

        stock_name = selected.split(" (")[0]

    else:

        ticker = query.upper()
        stock_name = query.upper()

        st.info("미국 종목 모드")

    st.divider()

    period = st.selectbox(
        "기간",
        ["6mo", "1y", "2y", "5y"],
        index=1
    )

    show_fib = st.checkbox(
        "피보나치 표시",
        value=True
    )

# =========================================================
# 메인
# =========================================================

data = fetch_data(ticker, period)

if data.empty:

    st.error("데이터를 불러오지 못했습니다.")

else:

    data = calculate_indicators(data)

    data = generate_signals(data)

    latest = data.iloc[-1]

    score = calculate_score(data)

    recommendation = recommendation_text(score)

    # =====================================================
    # 상단 제목
    # =====================================================

    st.title(f"📈 {stock_name} 전략 분석")

    # =====================================================
    # 메트릭
    # =====================================================

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "현재가",
        f"{latest['Close']:,.0f}"
    )

    c2.metric(
        "RSI",
        f"{latest['RSI']:.1f}"
    )

    c3.metric(
        "MACD",
        f"{latest['MACD']:.2f}"
    )

    c4.metric(
        "AI SCORE",
        f"{score}/100"
    )

    c5.metric(
        "전략판단",
        recommendation
    )

    # =====================================================
    # 피보나치 값
    # =====================================================

    fibs = {
        '0%': latest['Fib_0'],
        '23.6%': latest['Fib_236'],
        '38.2%': latest['Fib_382'],
        '50%': latest['Fib_500'],
        '61.8%': latest['Fib_618'],
        '78.6%': latest['Fib_786'],
        '100%': latest['Fib_100']
    }

    # =====================================================
    # 차트 생성
    # =====================================================

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.15, 0.15]
    )

    # =====================================================
    # 피보나치 영역
    # =====================================================

    if show_fib:

        levels = [

            (fibs['0%'], fibs['23.6%'], 'rgba(255,0,0,0.08)'),

            (fibs['23.6%'], fibs['38.2%'], 'rgba(255,165,0,0.08)'),

            (fibs['38.2%'], fibs['50%'], 'rgba(255,255,0,0.05)'),

            (fibs['50%'], fibs['61.8%'], 'rgba(0,255,0,0.08)'),

            (fibs['61.8%'], fibs['78.6%'], 'rgba(0,0,255,0.08)')
        ]

        for top, bottom, color in levels:

            fig.add_trace(
                go.Scatter(
                    x=data['Date'],
                    y=[top] * len(data),
                    line=dict(width=0),
                    showlegend=False
                ),
                row=1,
                col=1
            )

            fig.add_trace(
                go.Scatter(
                    x=data['Date'],
                    y=[bottom] * len(data),
                    fill='tonexty',
                    fillcolor=color,
                    line=dict(width=0),
                    showlegend=False
                ),
                row=1,
                col=1
            )

    # =====================================================
    # 캔들
    # =====================================================

    fig.add_trace(

        go.Candlestick(
            x=data['Date'],
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name="PRICE"
        ),

        row=1,
        col=1
    )

    # =====================================================
    # 이동평균선
    # =====================================================

    ma_colors = {
        'MA20': 'yellow',
        'MA60': 'cyan',
        'MA120': 'magenta'
    }

    for ma, color in ma_colors.items():

        fig.add_trace(

            go.Scatter(
                x=data['Date'],
                y=data[ma],
                name=ma,
                line=dict(color=color, width=1.5)
            ),

            row=1,
            col=1
        )

    # =====================================================
    # BUY SIGNAL
    # =====================================================

    buys = data[data['Buy_Signal']]

    fig.add_trace(

        go.Scatter(
            x=buys['Date'],
            y=buys['Low'] * 0.98,
            mode='markers+text',
            text=['BUY'] * len(buys),
            textposition='bottom center',
            marker=dict(
                symbol='star',
                size=14,
                color='lime'
            ),
            name='BUY SIGNAL'
        ),

        row=1,
        col=1
    )

    # =====================================================
    # SELL SIGNAL
    # =====================================================

    sells = data[data['Sell_Signal']]

    fig.add_trace(

        go.Scatter(
            x=sells['Date'],
            y=sells['High'] * 1.02,
            mode='markers+text',
            text=['SELL'] * len(sells),
            textposition='top center',
            marker=dict(
                symbol='x',
                size=12,
                color='red'
            ),
            name='SELL SIGNAL'
        ),

        row=1,
        col=1
    )

    # =====================================================
    # 거래량
    # =====================================================

    fig.add_trace(

        go.Bar(
            x=data['Date'],
            y=data['Volume'],
            marker_color='gray',
            name='VOLUME'
        ),

        row=2,
        col=1
    )

    # =====================================================
    # RSI
    # =====================================================

    fig.add_trace(

        go.Scatter(
            x=data['Date'],
            y=data['RSI'],
            line=dict(color='orange'),
            name='RSI'
        ),

        row=3,
        col=1
    )

    fig.add_hline(
        y=70,
        line_dash='dash',
        line_color='red',
        row=3,
        col=1
    )

    fig.add_hline(
        y=30,
        line_dash='dash',
        line_color='green',
        row=3,
        col=1
    )

    # =====================================================
    # 차트 설정
    # =====================================================

    fig.update_layout(

        template="plotly_dark",

        height=1000,

        xaxis_rangeslider_visible=False,

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # =====================================================
    # 전략 리포트
    # =====================================================

    st.divider()

    st.subheader("📋 AI 전략 분석")

    trend = "상승추세" if latest['MA20'] > latest['MA60'] else "하락추세"

    st.write(f"""
    ### 🔍 현재 분석

    - 현재 추세: **{trend}**
    - RSI 상태: **{latest['RSI']:.1f}**
    - MACD 상태: **{'상승 우위' if latest['MACD'] > latest['MACD_SIGNAL'] else '하락 우위'}**
    - 피보나치 핵심 지지선: **{latest['Fib_618']:,.0f}**
    - ATR 변동성: **{latest['ATR']:.2f}**
    - 종합 점수: **{score}/100**
    - 전략 판단: **{recommendation}**
    """)

    # =====================================================
    # 리스크 경고
    # =====================================================

    st.warning("""
    본 시스템은 투자 보조지표 분석용입니다.

    실제 투자에서는:
    - 시장 상황
    - 뉴스
    - 실적
    - 금리
    - 섹터 흐름
    을 반드시 함께 고려하세요.
    """)
