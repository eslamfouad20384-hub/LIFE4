import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🤖 Adaptive Grid System PRO (Stable + Smart Swing + 4 Modes)")

session = requests.Session()

# =========================
# 📊 DATA (Coinbase ONLY)
# =========================
@st.cache_data(ttl=120)
def get_data(symbol, target_candles=1000, granularity=3600):

    try:
        url = f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles"

        all_data = []
        end = None

        while len(all_data) < target_candles:

            params = {"granularity": granularity}
            if end:
                params["end"] = end

            r = session.get(url, params=params, timeout=10).json()

            if not isinstance(r, list) or len(r) == 0:
                break

            all_data.extend(r)

            oldest = min(r, key=lambda x: x[0])[0]
            end = oldest - granularity

            if len(r) < 2:
                break

        df = pd.DataFrame(all_data, columns=["time","low","high","open","close","volume"])

        df = df.drop_duplicates(subset=["time"])
        df = df.sort_values("time").reset_index(drop=True)

        for col in ["low","high","open","close","volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna().reset_index(drop=True)

        return df.tail(target_candles)

    except:
        return None


# =========================
# 📈 INDICATORS
# =========================
def add_indicators(df):

    df = df.reset_index(drop=True)

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
# 🧠 MARKET SCORE
# =========================
def analyze(df):

    latest = df.iloc[-1]

    score = 0
    reasons = []

    if latest["rsi"] < 35:
        score += 15
        reasons.append("RSI oversold +15")

    if latest["macd"] > latest["signal"]:
        score += 15
        reasons.append("MACD bullish +15")

    if latest["ema50"] > latest["ema200"]:
        score += 15
        reasons.append("Uptrend +15")

    if latest["volume"] > latest["vol_ma"]:
        score += 10
        reasons.append("Volume strong +10")

    if latest["close"] > df["close"].iloc[-5:].mean():
        score += 10
        reasons.append("Momentum +10")

    return score, reasons


# =========================
# 🔥 SMART SWING DETECTION
# =========================
def detect_levels(df, left=5, right=5):

    df = df.reset_index(drop=True)

    highs = df["high"].values
    lows = df["low"].values

    pivot_highs = []
    pivot_lows = []

    for i in range(left, len(df) - right):

        if all(highs[i] > highs[i - j] for j in range(1, left+1)) and \
           all(highs[i] > highs[i + j] for j in range(1, right+1)):
            pivot_highs.append(highs[i])

        if all(lows[i] < lows[i - j] for j in range(1, left+1)) and \
           all(lows[i] < lows[i + j] for j in range(1, right+1)):
            pivot_lows.append(lows[i])

    def filter_levels(levels):
        if len(levels) == 0:
            return []

        filtered = []
        threshold = np.std(levels) * 0.3

        for lvl in levels:
            if len(filtered) == 0:
                filtered.append(lvl)
            elif abs(lvl - np.mean(filtered)) > threshold:
                filtered.append(lvl)

        return filtered

    pivot_highs = filter_levels(pivot_highs)
    pivot_lows = filter_levels(pivot_lows)

    support = np.mean(pivot_lows[-3:]) if len(pivot_lows) >= 3 else df["low"].min()
    resistance = np.mean(pivot_highs[-3:]) if len(pivot_highs) >= 3 else df["high"].max()

    return support, resistance


# =========================
# 🤖 GRID MODES (NEW SYSTEM)
# =========================
def grid_mode(score):

    if score >= 75:
        return "HIGH"

    elif score >= 55:
        return "MEDIUM"

    elif score >= 40:
        return "LOW"

    elif score >= 25:
        return "WEAK"

    else:
        return "NO_TRADE"


# =========================
# 🤖 ADAPTIVE GRID ENGINE
# =========================
def grid_engine(df, score):

    latest = df.iloc[-1]

    support, resistance = detect_levels(df)

    atr = latest["atr"]
    price = latest["close"]

    low = support * 0.995
    high = resistance * 0.995

    if (high - low) < atr * 6:
        low = price - atr * 7
        high = price + atr * 7

    mode = grid_mode(score)

    volatility = atr / price

    if mode == "HIGH":
        grids = 60 if volatility > 0.03 else 45

    elif mode == "MEDIUM":
        grids = 35 if volatility > 0.03 else 25

    elif mode == "LOW":
        grids = 20 if volatility > 0.03 else 12

    elif mode == "WEAK":
        grids = 10 if volatility > 0.03 else 8

    else:
        grids = 0

    return low, high, int(grids), mode


# =========================
# 🚀 UI
# =========================
coin = st.text_input("🔎 Enter Coin (BTC, ETH, SOL...)")

if st.button("Analyze") and coin:

    df = get_data(coin.upper(), 1000)

    if df is None or df.empty:
        st.error("No data")
        st.stop()

    df = add_indicators(df)

    score, reasons = analyze(df)

    low, high, grids, mode = grid_engine(df, score)

    st.subheader("🤖 Mode")
    st.write(mode)

    if mode == "NO_TRADE":
        st.error("⚠️ No Trade - Market too weak")
        st.stop()

    st.subheader("📊 Grid Setup")
    st.write(f"Low: {low:.6f}")
    st.write(f"High: {high:.6f}")
    st.write(f"Grids: {grids}")

    st.subheader("🧠 Score")
    st.write(score)

    st.subheader("📌 Reasons")
    for r in reasons:
        st.write("•", r)
