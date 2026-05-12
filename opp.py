import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from plotly.subplots import make_subplots

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="PRO TRADING TERMINAL",
    layout="wide"
)

# =========================================================
# DATA
# =========================================================

@st.cache_data(ttl=300)
def load_data(ticker, period="2y"):

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

    # =========================
    # EMA TREND
    # =========================

    df['EMA20'] = df['Close'].ewm(span=20).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()
    df['EMA200'] = df['Close'].ewm(span=200).mean()

    # =========================
    # RSI
    # =========================

    delta = df['Close'].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss

    df['RSI'] = 100 - (100 / (1 + rs))

    # =========================
    # MACD
    # =========================

    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()

    df['MACD'] = ema12 - ema26
    df['MACD_SIGNAL'] = df['MACD'].ewm(span=9).mean()

    # =========================
    # ATR
    # =========================

    high_low = df['High'] - df['Low']

    high_close = abs(df['High'] - df['Close'].shift())
    low_close = abs(df['Low'] - df['Close'].shift())

    ranges = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    )

    tr = ranges.max(axis=1)

    df['ATR'] = tr.rolling(14).mean()

    # =========================
    # VOLUME
    # =========================

    df['VOL_MA20'] = df['Volume'].rolling(20).mean()

    # =========================
    # BOLLINGER
    # =========================

    ma20 = df['Close'].rolling(20).mean()
    std20 = df['Close'].rolling(20).std()

    df['BB_UPPER'] = ma20 + 2 * std20
    df['BB_LOWER'] = ma20 - 2 * std20
    df['BB_WIDTH'] = (
        (df['BB_UPPER'] - df['BB_LOWER']) / ma20
    )

    # =========================
    # ADX TREND STRENGTH
    # =========================

    plus_dm = df['High'].diff()
    minus_dm = -df['Low'].diff()

    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr14 = tr.rolling(14).sum()

    plus_di = 100 * (
        plus_dm.rolling(14).sum() / tr14
    )

    minus_di = 100 * (
        minus_dm.rolling(14).sum() / tr14
    )

    dx = (
        abs(plus_di - minus_di)
        / (plus_di + minus_di)
    ) * 100

    df['ADX'] = dx.rolling(14).mean()

    return df

# =========================================================
# MARKET REGIME
# =========================================================

def market_regime(df):

    latest = df.iloc[-1]

    if (
        latest['Close'] > latest['EMA200']
        and latest['ADX'] > 25
    ):
        return "BULL"

    elif (
        latest['Close'] < latest['EMA200']
        and latest['ADX'] > 25
    ):
        return "BEAR"

    else:
        return "SIDEWAYS"

# =========================================================
# SIGNAL ENGINE
# =========================================================

def signals(df):

    # =====================================
    # LONG ENTRY
    # =====================================

    df['BUY'] = (

        # 강한 추세
        (df['EMA20'] > df['EMA50']) &
        (df['EMA50'] > df['EMA200']) &

        # 추세 강도
        (df['ADX'] > 25) &

        # 모멘텀
        (df['MACD'] > df['MACD_SIGNAL']) &

        # 거래량 증가
        (df['Volume'] > df['VOL_MA20'] * 1.5) &

        # 변동성 압축 후 돌파
        (df['Close'] > df['BB_UPPER']) &

        # RSI 과열 회피
        (df['RSI'] > 55) &
        (df['RSI'] < 75)

    )

    # =====================================
    # EXIT
    # =====================================

    df['SELL'] = (

        (df['Close'] < df['EMA20']) |

        (df['MACD'] < df['MACD_SIGNAL']) |

        (df['RSI'] > 80)

    )

    return df

# =========================================================
# RISK MANAGEMENT
# =========================================================

def risk_management(df):

    latest = df.iloc[-1]

    entry = latest['Close']

    atr = latest['ATR']

    stop = entry - (2 * atr)

    target1 = entry + (2 * atr)
    target2 = entry + (4 * atr)

    rr = (target2 - entry) / (entry - stop)

    return {
        "entry": entry,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "rr": rr
    }

# =========================================================
# POSITION SIZING
# =========================================================

def position_size(account_size, risk_percent, entry, stop):

    risk_amount = account_size * risk_percent

    risk_per_share = abs(entry - stop)

    shares = risk_amount / risk_per_share

    return int(shares)

# =========================================================
# BACKTEST
# =========================================================

def backtest(df):

    capital = 10000000
    position = 0

    trades = []

    for i in range(1, len(df)):

        row = df.iloc[i]

        if position == 0 and row['BUY']:

            entry = row['Close']
            position = 1

        elif position == 1 and row['SELL']:

            exit_price = row['Close']

            pnl = (
                (exit_price - entry)
                / entry
            )

            trades.append(pnl)

            position = 0

    if len(trades) == 0:

        return {
            "winrate": 0,
            "avg": 0,
            "trades": 0
        }

    wins = [x for x in trades if x > 0]

    return {
        "winrate": round(
            len(wins) / len(trades) * 100,
            2
        ),
        "avg": round(
            np.mean(trades) * 100,
            2
        ),
        "trades": len(trades)
    }

# =========================================================
# UI
# =========================================================

ticker = st.sidebar.text_input(
    "Ticker",
    "AAPL"
)

df = load_data(ticker)

df = indicators(df)

df = signals(df)

latest = df.iloc[-1]

regime = market_regime(df)

risk = risk_management(df)

bt = backtest(df)

# =========================================================
# DASHBOARD
# =========================================================

st.title("🔥 PROFESSIONAL TRADING TERMINAL")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "MARKET REGIME",
    regime
)

c2.metric(
    "ADX",
    f"{latest['ADX']:.1f}"
)

c3.metric(
    "RSI",
    f"{latest['RSI']:.1f}"
)

c4.metric(
    "WIN RATE",
    f"{bt['winrate']}%"
)

# =========================================================
# RISK TABLE
# =========================================================

st.subheader("RISK MANAGEMENT")

shares = position_size(
    10000000,
    0.01,
    risk['entry'],
    risk['stop']
)

st.write(f"""
ENTRY : {risk['entry']:.2f}

STOP : {risk['stop']:.2f}

TARGET1 : {risk['target1']:.2f}

TARGET2 : {risk['target2']:.2f}

R/R : {risk['rr']:.2f}

POSITION SIZE : {shares} shares
""")

# =========================================================
# CHART
# =========================================================

fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=[0.8, 0.2]
)

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

for ema in ['EMA20', 'EMA50', 'EMA200']:

    fig.add_trace(

        go.Scatter(
            x=df['Date'],
            y=df[ema],
            name=ema
        ),

        row=1,
        col=1
    )

buys = df[df['BUY']]

fig.add_trace(

    go.Scatter(
        x=buys['Date'],
        y=buys['Low'] * 0.98,
        mode='markers',
        marker=dict(
            size=12,
            symbol='triangle-up'
        ),
        name='BUY'
    ),

    row=1,
    col=1
)

fig.add_trace(

    go.Bar(
        x=df['Date'],
        y=df['Volume'],
        name='Volume'
    ),

    row=2,
    col=1
)

fig.update_layout(
    template='plotly_dark',
    height=900,
    xaxis_rangeslider_visible=False
)

st.plotly_chart(
    fig,
    use_container_width=True
)
