import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🤖 HYBRID GRID PRO SYSTEM (Scanner + Swing + AI Mode)")

session = requests.Session()

# =========================
# ⚡ FAST SCANNER (TOP COINS)
# =========================
@st.cache_data(ttl=300)
def get_top_coins():
    try:
        url = "https://api.exchange.coinbase.com/products"
        r = session.get(url, timeout=10).json()

        coins = []
        for item in r:
            if item["quote_currency"] == "USD":
                coins.append(item["id"])

        coins = coins[:80]

        volumes = []

        for symbol in coins:
            try:
                url2 = f"https://api.exchange.coinbase.com/products/{symbol}/ticker"
                data = session.get(url2, timeout=5).json()

                if "volume" in data:
                    volumes.append((symbol.replace("-USD",""), float(data["volume"])))
            except:
                pass

        volumes.sort(key=lambda x: x[1], reverse=True)

        return [x[0] for x in volumes[:20]]

    except:
        return []


# =========================
# 📊 GET CANDLES (FAST)
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
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    rs = pd.Series(gain).ewm(alpha=1/14).mean() / (pd.Series(loss).ewm(alpha=1/14).mean() + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()

    df["macd"] = ema12 - ema26
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
# 🧠 SWING LEVELS
# =========================
def swing_levels(df, left=5, right=5):

    highs = df["high"].values
    lows = df["low"].values

    ph = []
    pl = []

    for i in range(left, len(df)-right):

        if all(highs[i] > highs[i-j] for j in range(1,left+1)) and \
           all(highs[i] > highs[i+j] for j in range(1,right+1)):
            ph.append(highs[i])

        if all(lows[i] < lows[i-j] for j in range(1,left+1)) and \
           all(lows[i] < lows[i+j] for j in range(1,right+1)):
            pl.append(lows[i])

    support = np.mean(pl[-3:]) if len(pl) >= 3 else df["low"].min()
    resistance = np.mean(ph[-3:]) if len(ph) >= 3 else df["high"].max()

    return support, resistance


# =========================
# 🧠 SCORE ENGINE
# =========================
def score(df):

    l = df.iloc[-1]
    s = 0
    r = []

    if l["rsi"] < 40:
        s += 15; r.append("RSI good")

    if l["macd"] > l["signal"]:
        s += 15; r.append("MACD bullish")

    if l["ema50"] > l["ema200"]:
        s += 15; r.append("Uptrend")

    if l["volume"] > l["vol_ma"]:
        s += 10; r.append("Volume spike")

    if abs(l["ema50"] - l["ema200"]) / l["close"] < 0.02:
        s += 10; r.append("Sideways structure")

    if l["atr"] / l["close"] > 0.015:
        s += 10; r.append("Volatility OK")

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
def grid(df, score):

    l = df.iloc[-1]

    support, resistance = swing_levels(df)

    price = l["close"]
    atr = l["atr"]

    low = support
    high = resistance

    if high - low < atr * 5:
        low = price - atr * 6
        high = price + atr * 6

    m = mode(score)
    vol = atr / price

    if m == "STRONG":
        grids = 50 if vol > 0.03 else 35
    elif m == "GOOD":
        grids = 30
    elif m == "OK":
        grids = 18
    elif m == "WEAK":
        grids = 10
    else:
        grids = 0

    return low, high, grids, m


# =========================
# 🚀 MAIN SCANNER
# =========================
if st.button("🔥 Find Best Hybrid GRID Coin"):

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

        if sc < 40:
            continue

        results.append({
            "Coin": c,
            "Score": sc
        })

    if results:
        table = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.dataframe(table)

        best = table.iloc[0]["Coin"]
        st.success(f"🔥 BEST COIN: {best}")

    else:
        st.warning("No good opportunities")


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
        st.error("Market not suitable")
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
