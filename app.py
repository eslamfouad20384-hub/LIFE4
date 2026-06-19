import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🤖 HYBRID GRID PRO SYSTEM (AI + Smart Selection)")

session = requests.Session()

# =========================
# 🧠 TOP 100 COINS (REAL MARKET)
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
# 📈 INDICATORS (FIXED RSI)
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
# 🧠 SWING LEVELS (IMPROVED)
# =========================
def swing_levels(df):
    highs = df["high"].values
    lows = df["low"].values

    ph = []
    pl = []

    for i in range(5, len(df)-5):
        if highs[i] == max(highs[i-5:i+6]):
            ph.append(highs[i])

        if lows[i] == min(lows[i-5:i+6]):
            pl.append(lows[i])

    support = np.median(pl[-5:]) if len(pl) else df["low"].min()
    resistance = np.median(ph[-5:]) if len(ph) else df["high"].max()

    return support, resistance


# =========================
# 🧠 SCORE (GRID FILTER)
# =========================
def score(df):
    l = df.iloc[-1]
    s = 0
    r = []

    # RSI (neutral grid zone only)
    if 40 < l["rsi"] < 65:
        s += 20; r.append("RSI neutral zone")
    elif l["rsi"] < 35:
        s += 10; r.append("oversold support zone")

    # MACD
    if l["macd"] > l["signal"]:
        s += 10; r.append("MACD bullish")

    # Trend filter (IMPORTANT)
    trend_strength = abs(l["ema50"] - l["ema200"]) / l["close"]
    if trend_strength < 0.015:
        s += 25; r.append("Sideways market (ideal grid)")
    else:
        s -= 20; r.append("Trending market (risky grid)")

    # Volume
    if l["volume"] > l["vol_ma"]:
        s += 10; r.append("Volume active")

    # Volatility
    if l["atr"] / l["close"] > 0.01:
        s += 10; r.append("Enough volatility")

    return s, r


# =========================
# 🤖 GRID MODE
# =========================
def mode(s):
    if s >= 70:
        return "STRONG"
    elif s >= 55:
        return "GOOD"
    elif s >= 40:
        return "OK"
    elif s >= 25:
        return "WEAK"
    else:
        return "NO_TRADE"


# =========================
# 📦 GRID ENGINE
# =========================
def grid(df, sc):
    l = df.iloc[-1]

    support, resistance = swing_levels(df)
    price = l["close"]
    atr = l["atr"]

    low, high = support, resistance

    if high - low < atr * 5:
        low = price - atr * 6
        high = price + atr * 6

    m = mode(sc)
    vol = atr / price

    if m == "STRONG":
        grids = 40 if vol > 0.03 else 30
    elif m == "GOOD":
        grids = 25
    elif m == "OK":
        grids = 15
    elif m == "WEAK":
        grids = 8
    else:
        grids = 0

    return low, high, grids, m


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
        st.warning("No good grid setups")

# =========================
# 🔍 SINGLE ANALYSIS
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

    st.subheader("Mode")
    st.write(m)

    if m == "NO_TRADE":
        st.error("Market not suitable for GRID")
        st.stop()

    st.subheader("Grid Levels")
    st.write(f"Low: {low:.4f}")
    st.write(f"High: {high:.4f}")
    st.write(f"Grids: {grids}")

    st.subheader("Score")
    st.write(sc)

    st.subheader("Reasons")
    for r in reasons:
        st.write("•", r)
