import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🤖 HYBRID GRID PRO SYSTEM (Wide + Narrow + Auto Range)")

session = requests.Session()

# =========================
# 🧠 TOP COINS
# =========================
@st.cache_data(ttl=600)
def get_top_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 100,
        "page": 1
    }

    r = session.get(url, params=params, timeout=10).json()
    return [x["symbol"].upper() for x in r]


# =========================
# 📊 DATA
# =========================
@st.cache_data(ttl=120)
def get_data(symbol, candles=250):
    try:
        url = f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles"
        data = session.get(url, params={"granularity": 3600}, timeout=10).json()

        if not isinstance(data, list):
            return None

        df = pd.DataFrame(data, columns=["time","low","high","open","close","volume"])
        df = df.sort_values("time").reset_index(drop=True)

        for c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        return df.tail(candles).dropna()

    except:
        return None


# =========================
# 📈 INDICATORS
# =========================
def indicators(df):

    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/14).mean()
    avg_loss = loss.ewm(alpha=1/14).mean()

    rs = avg_gain / (avg_loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    df["macd"] = df["close"].ewm(span=12).mean() - df["close"].ewm(span=26).mean()
    df["signal"] = df["macd"].ewm(span=9).mean()

    df["vol_ma"] = df["volume"].rolling(20).mean()

    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)

    df["atr"] = tr.rolling(14).mean()

    return df.dropna().reset_index(drop=True)


# =========================
# 🧠 MARKET MODE (AUTO)
# =========================
def market_mode(df):
    l = df.iloc[-1]

    trend = abs(l["ema50"] - l["ema200"]) / l["close"]
    rsi = l["rsi"]

    if trend < 0.012 and 40 < rsi < 60:
        return "SIDEWAYS_STRONG"
    elif trend < 0.02:
        return "MIXED"
    else:
        return "TRENDING"


# =========================
# 📊 AUTO RANGE DETECTION
# =========================
def auto_range(df):
    l = df.iloc[-1]

    atr = l["atr"]
    price = l["close"]

    high = df["high"].rolling(20).max().iloc[-1]
    low = df["low"].rolling(20).min().iloc[-1]

    if (high - low) < atr * 3:
        low = price - atr * 6
        high = price + atr * 6

    return low, high


# =========================
# 🧠 SCORE ENGINE
# =========================
def score(df):
    l = df.iloc[-1]
    s = 0
    r = []

    if 40 < l["rsi"] < 65:
        s += 20; r.append("RSI neutral")

    if l["macd"] > l["signal"]:
        s += 10; r.append("MACD bullish")

    trend = abs(l["ema50"] - l["ema200"]) / l["close"]

    if trend < 0.015:
        s += 25; r.append("Sideways market")
    else:
        s -= 20; r.append("Trending risk")

    if l["volume"] > l["vol_ma"]:
        s += 10; r.append("Volume active")

    if l["atr"] / l["close"] > 0.01:
        s += 10; r.append("Volatility OK")

    return s, r


# =========================
# 🤖 GRID ENGINE (WIDE + NARROW)
# =========================
def grid(df, sc):

    l = df.iloc[-1]

    mode = market_mode(df)
    low, high = auto_range(df)

    price = l["close"]
    atr = l["atr"]

    # =========================
    # GRID LOGIC
    # =========================

    if mode == "SIDEWAYS_STRONG":
        grid_type = "NARROW_GRID"
        grids = 45
        step = atr * 0.8

    elif mode == "MIXED":
        grid_type = "WIDE_GRID"
        grids = 25
        step = atr * 1.5

    else:
        grid_type = "NO_GRID"
        grids = 0
        step = 0

    # safety range fix
    if grid_type != "NO_GRID":
        if high - low < atr * 5:
            low = price - atr * 5
            high = price + atr * 5

    return low, high, grids, grid_type


# =========================
# 🚀 SCANNER
# =========================
if st.button("🔥 Find Best GRID Coin"):

    coins = get_top_coins()
    results = []

    for c in coins:

        df = get_data(c, 250)
        if df is None or len(df) < 120:
            continue

        df = indicators(df)
        if len(df) < 50:
            continue

        sc, _ = score(df)

        if sc < 45:
            continue

        results.append({"Coin": c, "Score": sc})

    if results:
        table = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.dataframe(table)

        best = table.iloc[0]["Coin"]
        st.success(f"🔥 BEST GRID COIN: {best}")
    else:
        st.warning("No good setups")


# =========================
# 🔍 ANALYZE SINGLE COIN
# =========================
coin = st.text_input("Enter Coin (BTC, ETH, SOL...)")

if st.button("Analyze") and coin:

    df = get_data(coin.upper(), 250)

    if df is None:
        st.error("No data")
        st.stop()

    df = indicators(df)

    sc, reasons = score(df)
    low, high, grids, m = grid(df, sc)

    st.subheader("Market Mode")
    st.write(m)

    if m == "NO_GRID":
        st.error("Market trending → No Grid allowed")
        st.stop()

    st.subheader("Grid Range")
    st.write(f"Low: {low:.4f}")
    st.write(f"High: {high:.4f}")
    st.write(f"Grids: {grids}")

    st.subheader("Score")
    st.write(sc)

    st.subheader("Reasons")
    for r in reasons:
        st.write("•", r)
