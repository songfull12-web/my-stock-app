import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

import plotly.graph_objects as go

from plotly.subplots import make_subplots

# =========================================================
# PAGE CONFIG
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

.metric-card {
    background-color: #111;
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #333;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# KRX MASTER
# =========================================================

@st.cache_data(show_spinner="KRX 종목 불러오는 중...")
def load_krx():

    try:

        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"

        df = pd.read_csv(url)

        return df[['Symbol', 'Name', 'Market']]

    except:

        return pd.DataFrame([
            {
                "Symbol": "005930",
                "Name": "삼성전자",
                "Market": "KOSPI"
            }
        ])

master = load_krx()

# =========================================================
# DATA LOAD
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
    df['EMA200'] = df['Close'].ewm(span=200).mean()

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

    # BOLLINGER
    ma20 = df['Close'].rolling(20).mean()
    std20 = df['Close'].rolling(20).std()

    df['BB_UPPER'] = ma20 + (std20 * 2)
    df['BB_LOWER'] = ma20 - (std20 * 2)

    # ADX
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

    # =====================================================
    # FIBONACCI
    # =====================================================

    recent = df.tail(120)

    hp = recent['High'].max()
    lp = recent['Low'].min()

    diff = hp - lp

    df['Fib_0'] = hp
    df['Fib_236'] = hp - (0.236 * diff)
    df['Fib_382'] = hp - (0.382 * diff)
    df['Fib_500'] = hp - (0.5 * diff)
    df['Fib_618'] = hp - (0.618 * diff)
    df['Fib_786'] = hp - (0.786 * diff)
    df['Fib_100'] = lp

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

        return "🔥 강세장"

    elif (
        latest['Close'] < latest['EMA200']
        and latest['ADX'] > 25
    ):

        return "❄ 약세장"

    else:

        return "⚠ 횡보장"

# =========================================================
# SIGNAL ENGINE
# =========================================================

def signals(df):

    df['BUY'] = (

        (df['EMA20'] > df['EMA60']) &

        (df['Close'] > df['EMA20']) &

        (df['ADX'] > 20) &

        (df['MACD'] > df['MACD_SIGNAL']) &

        (df['Volume'] > df['VOL_MA20'] * 1.3) &

        (df['RSI'] > 50) &
        (df['RSI'] < 72) &

        (df['Close'] > df['Fib_618'])

    )

    df['SELL'] = (

        (df['MACD'] < df['MACD_SIGNAL']) |

        (df['RSI'] > 80) |

        (df['Close'] < df['EMA20'])

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

    if latest['ADX'] > 20:
        s += 20

    if latest['Volume'] > latest['VOL_MA20']:
        s += 20

    return s

# =========================================================
# RECOMMEND
# =========================================================

def recommendation(score):

    if score >= 80:
        return "🔥 강력매수"

    elif score >= 60:
        return "✅ 매수유망"

    elif score >= 40:
        return "⚠ 관망"

    else:
        return "❌ 비추천"

# =========================================================
# BACKTEST
# =========================================================

def backtest(df):

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

        return 0, 0

    winrate = (
        len([x for x in trades if x > 0])
        / len(trades)
    ) * 100

    avg = np.mean(trades) * 100

    return round(winrate, 2), round(avg, 2)

# =========================================================
# RISK
# =========================================================

def risk(df):

    latest = df.iloc[-1]

    entry = latest['Close']

    atr = latest['ATR']

    stop = entry - (2 * atr)

    target = entry + (4 * atr)

    rr = (
        (target - entry)
        / (entry - stop)
    )

    return entry, stop, target, rr

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("🔥 PRO TERMINAL")

    query = st.text_input(
        "종목 검색",
        value="삼성"
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

        stock_code = (
            selected.split("(")[1]
            .replace(")", "")
        )

        market = matches[
            matches['Symbol'] == stock_code
        ].iloc[0]['Market']

        ticker = (
            f"{stock_code}.KS"
            if market == "KOSPI"
            else f"{stock_code}.KQ"
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
# MAIN
# =========================================================

df = load_data(ticker, period)

if df.empty:

    st.error("데이터 로딩 실패")

else:

    df = indicators(df)

    df = signals(df)

    latest = df.iloc[-1]

    s = score(df)

    reco = recommendation(s)

    regime = market_regime(df)

    winrate, avg = backtest(df)

    entry, stop, target, rr = risk(df)

    # =====================================================
    # TITLE
    # =====================================================

    st.title(f"📈 {stock_name} PRO 전략분석")

    # =====================================================
    # METRICS
    # =====================================================

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric(
        "현재가",
        f"{latest['Close']:,.0f}"
    )

    c2.metric(
        "RSI",
        f"{latest['RSI']:.1f}"
    )

    c3.metric(
        "ADX",
        f"{latest['ADX']:.1f}"
    )

    c4.metric(
        "AI SCORE",
        f"{s}/100"
    )

    c5.metric(
        "시장상태",
        regime
    )

    c6.metric(
        "전략판단",
        reco
    )

    # =====================================================
    # FIB LEVELS
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
    # FIBONACCI ZONE
    # =====================================================

    levels = [

        (fibs['0%'], fibs['23.6%'], 'rgba(255,0,0,0.08)'),

        (fibs['23.6%'], fibs['38.2%'], 'rgba(255,165,0,0.08)'),

        (fibs['38.2%'], fibs['50%'], 'rgba(255,255,0,0.06)'),

        (fibs['50%'], fibs['61.8%'], 'rgba(0,255,0,0.06)'),

        (fibs['61.8%'], fibs['78.6%'], 'rgba(0,0,255,0.06)')
    ]

    for top, bottom, color in levels:

        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=[top] * len(df),
                line=dict(width=0),
                showlegend=False
            ),
            row=1,
            col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=[bottom] * len(df),
                fill='tonexty',
                fillcolor=color,
                line=dict(width=0),
                showlegend=False
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

    # EMA
    for ema in ['EMA20', 'EMA60', 'EMA120']:

        fig.add_trace(

            go.Scatter(
                x=df['Date'],
                y=df[ema],
                name=ema
            ),

            row=1,
            col=1
        )

    # BUY
    buys = df[df['BUY']]

    fig.add_trace(

        go.Scatter(
            x=buys['Date'],
            y=buys['Low'] * 0.98,
            mode='markers+text',
            text=['BUY'] * len(buys),
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

    # SELL
    sells = df[df['SELL']]

    fig.add_trace(

        go.Scatter(
            x=sells['Date'],
            y=sells['High'] * 1.02,
            mode='markers+text',
            text=['SELL'] * len(sells),
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

    # VOLUME
    fig.add_trace(

        go.Bar(
            x=df['Date'],
            y=df['Volume'],
            name='VOLUME'
        ),

        row=2,
        col=1
    )

    # RSI
    fig.add_trace(

        go.Scatter(
            x=df['Date'],
            y=df['RSI'],
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

    fig.update_layout(

        template='plotly_dark',

        height=1100,

        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # =====================================================
    # STRATEGY REPORT
    # =====================================================

    st.divider()

    st.subheader("📋 AI 전략 분석")

    st.write(f"""

### 🔥 현재 시장 분석

- 시장 상태: **{regime}**
- 현재가: **{latest['Close']:,.0f}**
- RSI: **{latest['RSI']:.1f}**
- ADX: **{latest['ADX']:.1f}**
- MACD 상태: **{'상승 우위' if latest['MACD'] > latest['MACD_SIGNAL'] else '하락 우위'}**
- 피보나치 핵심지지: **{latest['Fib_618']:,.0f}**
- ATR 변동성: **{latest['ATR']:.2f}**
- 전략 점수: **{s}/100**
- 전략 판단: **{reco}**

---

### 🎯 리스크 관리

- 추천 진입가: **{entry:,.0f}**
- 손절가: **{stop:,.0f}**
- 목표가: **{target:,.0f}**
- 손익비(RR): **{rr:.2f}**

---

### 📊 백테스트 결과

- 승률: **{winrate}%**
- 평균 수익률: **{avg}%**

""")

    # =====================================================
    # INDICATOR GUIDE
    # =====================================================

    st.divider()

    st.subheader("📚 지표 설명")

    st.write("""

### RSI
- 70 이상 → 과열 가능성
- 30 이하 → 과매도 가능성
- 50 이상 유지 → 상승 추세 우위

### MACD
- MACD > SIGNAL → 상승 모멘텀
- MACD < SIGNAL → 하락 모멘텀

### ADX
- 20 이하 → 횡보 가능성
- 25 이상 → 강한 추세 발생

### ATR
- 변동성 지표
- ATR 높을수록 손절 폭 넓혀야 함

### 피보나치
- 61.8% 구간은 기관들이 많이 보는 핵심 되돌림 구간
- 가격이 61.8 위 유지 시 강세 지속 확률 증가

""")

    # =====================================================
    # WARNING
    # =====================================================

    st.warning("""

본 시스템은 실전 보조 시스템입니다.

반드시:
- 뉴스
- 실적
- 금리
- 시장 방향
- 섹터 흐름
- 외국인 수급

을 함께 고려하세요.

""")
