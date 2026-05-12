import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

import plotly.graph_objects as go

from plotly.subplots import make_subplots

from scipy.signal import argrelextrema
from sklearn.linear_model import LinearRegression

# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="PRO TRADING TERMINAL",
    layout="wide"
)

# =========================================================
# STYLE
# =========================================================

st.markdown("""
<style>

html, body, [class*="css"] {
    background-color: #0e1117;
    color: white;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# KRX DB
# =========================================================

@st.cache_data
def load_krx():

    url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"

    df = pd.read_csv(url)

    return df[['Symbol', 'Name', 'Market']]

master = load_krx()

# =========================================================
# LOAD DATA
# =========================================================

@st.cache_data(ttl=300)
def load_data(ticker, period):

    df = yf.download(
        ticker,
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.reset_index(inplace=True)

    return df

# =========================================================
# INDICATORS
# =========================================================

def indicators(df):

    # EMA
    df['EMA20'] = df['Close'].ewm(span=20).mean()
    df['EMA60'] = df['Close'].ewm(span=60).mean()
    df['EMA120'] = df['Close'].ewm(span=120).mean()

    # RSI
    delta = df['Close'].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()

    df['MACD'] = ema12 - ema26
    df['MACD_SIGNAL'] = df['MACD'].ewm(span=9).mean()

    # VOLUME
    df['VOL_MA20'] = df['Volume'].rolling(20).mean()

    # ATR
    high_low = df['High'] - df['Low']

    high_close = abs(df['High'] - df['Close'].shift())
    low_close = abs(df['Low'] - df['Close'].shift())

    ranges = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    )

    tr = ranges.max(axis=1)

    df['ATR'] = tr.rolling(14).mean()

    # =====================================================
    # FIBONACCI
    # =====================================================

    recent = df.tail(120)

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
# TREND LINE
# =========================================================

def trend_line(df):

    highs = argrelextrema(
        df['High'].values,
        np.greater,
        order=10
    )[0]

    lows = argrelextrema(
        df['Low'].values,
        np.less,
        order=10
    )[0]

    trend = {}

    # 상단 추세선
    if len(highs) >= 2:

        x = np.array(highs).reshape(-1, 1)
        y = df.iloc[highs]['High'].values

        model = LinearRegression()
        model.fit(x, y)

        trend['upper'] = model.predict(
            np.arange(len(df)).reshape(-1, 1)
        )

    # 하단 추세선
    if len(lows) >= 2:

        x = np.array(lows).reshape(-1, 1)
        y = df.iloc[lows]['Low'].values

        model = LinearRegression()
        model.fit(x, y)

        trend['lower'] = model.predict(
            np.arange(len(df)).reshape(-1, 1)
        )

    return trend

# =========================================================
# SIGNAL
# =========================================================

def signals(df):

    df['BUY'] = (

        (df['EMA20'] > df['EMA60']) &

        (df['Close'] > df['EMA20']) &

        (df['MACD'] > df['MACD_SIGNAL']) &

        (df['RSI'] > 50) &
        (df['RSI'] < 72) &

        (df['Volume'] > df['VOL_MA20']) &

        (df['Close'] > df['Fib_618'])

    )

    df['SELL'] = (

        (df['MACD'] < df['MACD_SIGNAL']) |

        (df['Close'] < df['EMA20']) |

        (df['RSI'] > 80)

    )

    return df

# =========================================================
# SCORE
# =========================================================

def score(df):

    latest = df.iloc[-1]

    s = 0

    if latest['Close'] > latest['EMA20']:
        s += 20

    if latest['EMA20'] > latest['EMA60']:
        s += 20

    if latest['MACD'] > latest['MACD_SIGNAL']:
        s += 20

    if latest['RSI'] > 50:
        s += 20

    if latest['Volume'] > latest['VOL_MA20']:
        s += 20

    return s

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("🔥 PRO TERMINAL")

    query = st.text_input(
        "종목 검색",
        "삼성"
    )

    matches = master[
        master['Name'].str.contains(
            query,
            case=False,
            na=False
        )
    ]

    if not matches.empty:

        options = [
            f"{r['Name']} ({r['Symbol']})"
            for _, r in matches.iterrows()
        ]

        selected = st.selectbox(
            "종목 선택",
            options
        )

        code = (
            selected.split("(")[1]
            .replace(")", "")
        )

        market = matches[
            matches['Symbol'] == code
        ].iloc[0]['Market']

        ticker = (
            f"{code}.KS"
            if market == "KOSPI"
            else f"{code}.KQ"
        )

        stock_name = selected.split(" (")[0]

    else:

        ticker = query.upper()
        stock_name = query.upper()

    period = st.selectbox(
        "기간",
        ["6mo", "1y", "2y", "5y"],
        index=2
    )

# =========================================================
# LOAD
# =========================================================

df = load_data(ticker, period)

if df.empty:

    st.error("데이터 불러오기 실패")

else:

    df = indicators(df)

    df = signals(df)

    trend = trend_line(df)

    latest = df.iloc[-1]

    ai_score = score(df)

    # =====================================================
    # TITLE
    # =====================================================

    st.title(f"📈 {stock_name} PRO ANALYSIS")

    # =====================================================
    # METRIC
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
        "ATR",
        f"{latest['ATR']:.2f}"
    )

    c5.metric(
        "AI SCORE",
        f"{ai_score}/100"
    )

    # =====================================================
    # CHART
    # =====================================================

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.15, 0.15]
    )

    # =====================================================
    # FIBONACCI
    # =====================================================

    fib_levels = [

        ('Fib_0', 'red'),
        ('Fib_236', 'orange'),
        ('Fib_382', 'yellow'),
        ('Fib_500', 'white'),
        ('Fib_618', 'cyan'),
        ('Fib_786', 'blue'),
        ('Fib_100', 'green')
    ]

    for fib, color in fib_levels:

        fig.add_trace(

            go.Scatter(
                x=df['Date'],
                y=df[fib],
                name=fib,
                line=dict(
                    dash='dot',
                    color=color
                )
            ),

            row=1,
            col=1
        )

    # =====================================================
    # CANDLE
    # =====================================================

    fig.add_trace(

        go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='PRICE'
        ),

        row=1,
        col=1
    )

    # =====================================================
    # EMA
    # =====================================================

    ema_colors = {
        'EMA20': 'yellow',
        'EMA60': 'cyan',
        'EMA120': 'magenta'
    }

    for ema, color in ema_colors.items():

        fig.add_trace(

            go.Scatter(
                x=df['Date'],
                y=df[ema],
                name=ema,
                line=dict(
                    width=2,
                    color=color
                )
            ),

            row=1,
            col=1
        )

    # =====================================================
    # TREND LINE
    # =====================================================

    if 'upper' in trend:

        fig.add_trace(

            go.Scatter(
                x=df['Date'],
                y=trend['upper'],
                name='UPPER TREND',
                line=dict(
                    color='red',
                    width=2
                )
            ),

            row=1,
            col=1
        )

    if 'lower' in trend:

        fig.add_trace(

            go.Scatter(
                x=df['Date'],
                y=trend['lower'],
                name='LOWER TREND',
                line=dict(
                    color='lime',
                    width=2
                )
            ),

            row=1,
            col=1
        )

    # =====================================================
    # BUY
    # =====================================================

    buys = df[df['BUY']]

    fig.add_trace(

        go.Scatter(
            x=buys['Date'],
            y=buys['Low'] * 0.98,
            mode='markers+text',
            text=['BUY'] * len(buys),
            textposition='bottom center',
            marker=dict(
                color='lime',
                size=14,
                symbol='triangle-up'
            ),
            name='BUY'
        ),

        row=1,
        col=1
    )

    # =====================================================
    # SELL
    # =====================================================

    sells = df[df['SELL']]

    fig.add_trace(

        go.Scatter(
            x=sells['Date'],
            y=sells['High'] * 1.02,
            mode='markers+text',
            text=['SELL'] * len(sells),
            textposition='top center',
            marker=dict(
                color='red',
                size=12,
                symbol='x'
            ),
            name='SELL'
        ),

        row=1,
        col=1
    )

    # =====================================================
    # VOLUME
    # =====================================================

    fig.add_trace(

        go.Bar(
            x=df['Date'],
            y=df['Volume'],
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
            x=df['Date'],
            y=df['RSI'],
            name='RSI',
            line=dict(color='orange')
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

    fig.update_layout(

        template='plotly_dark',

        height=1200,

        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # =====================================================
    # REPORT
    # =====================================================

    st.subheader("📋 전략 분석")

    st.write(f"""

### 현재 상태

- 현재가: {latest['Close']:,.0f}
- RSI: {latest['RSI']:.1f}
- MACD: {latest['MACD']:.2f}
- ATR: {latest['ATR']:.2f}

### 전략

- EMA20 위 → 단기 상승 우위
- EMA60 위 → 중기 상승 유지
- Fib 61.8 위 유지 시 강세 가능성
- 거래량 증가 여부 중요

### AI SCORE

- {ai_score}/100

""")

    # =====================================================
    # GUIDE
    # =====================================================

    st.subheader("📚 지표 설명")

    st.write("""

### RSI
- 70 이상 → 과열 가능성
- 30 이하 → 과매도

### MACD
- 상승 모멘텀 판단

### EMA
- 추세 방향 확인

### ATR
- 변동성 측정

### 피보나치
- 기관들이 많이 보는 되돌림 구간

### 추세선
- 지지/저항 시각화

""")
