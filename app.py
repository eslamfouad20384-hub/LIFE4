import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🤖 Adaptive Grid Engine PRO")

session = requests.Session()

# =========================
# 📊 DATA LOADER (Coinbase ONLY)
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

        return df.dropna().tail(target_candles)

    except:
        return None


# =========================
# 📈 INDICATORS
# =========================
def add_indicators(df):

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

    return df.dropna()


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
        reasons.append("Momentum up +10")

    return score, reasons


# =========================
# 📉 SUPPORT / RESISTANCE (Pivot Style)
# =========================
def detect_levels(df, left=5, right=5):

    highs = df["high"]
    lows = df["low"]

    support_levels = []
    resistance_levels = []

    for i in range(left, len(df) - right):

        if lows[i] == min(lows[i-left:i+right+1]):
            support_levels.append(lows[i])

        if highs[i] == max(highs[i-left:i+right+1]):
            resistance_levels.append(highs[i])

    support = np.mean(support_levels[-3:]) if support_levels else df["low"].min()
    resistance = np.mean(resistance_levels[-3:]) if resistance_levels else df["high"].max()

    return support, resistance


# =========================
# 🤖 ADAPTIVE GRID SYSTEM (MAIN ENGINE)
# =========================
def grid_engine(df, score):

    latest = df.iloc[-1]

    support, resistance = detect_levels(df)

    atr = latest["atr"]
    price = latest["close"]

    # 📉 Dynamic range
    low = support * 0.995
    high = resistance * 1.005

    min_range = atr * 6

    if (high - low) < min_range:
        low = price - atr * 7
        high = price + atr * 7

    # 📊 volatility
    volatility = atr / price

    # 🔢 base grids
    if volatility < 0.02:
        grids = 18
    elif volatility < 0.05:
        grids = 35
    else:
        grids = 55

    # 🧠 Adaptive adjustment (CORE FEATURE)
    if score >= 75:
        grids += 10
    elif score < 50:
        grids -= 10

    grids = max(10, min(80, grids))

    return low, high, int(grids)


# =========================
# 🧠 GRID DECISION LAYER
# =========================
def grid_decision(score):

    if score >= 75:
        return "STRONG_GRID"
    elif score >= 60:
        return "NORMAL_GRID"
    elif score >= 50:
        return "REDUCED_GRID"
    else:
        return "NO_GRID"


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
    decision = grid_decision(score)

    if decision == "NO_GRID":
        st.error("⚠️ Market not suitable for Grid")
        st.stop()

    low, high, grids = grid_engine(df, score)

    latest = df.iloc[-1]

    # =========================
    st.subheader("📊 Market Score")
    st.write(score)
    st.write(decision)

    # =========================
    st.subheader("🤖 Adaptive Grid Output")
    st.write(f"📉 Low: {low:.6f}")
    st.write(f"📈 High: {high:.6f}")
    st.write(f"🔢 Grids: {grids}")

    # =========================
    st.subheader("🧠 Reasons")
    for r in reasons:
        st.write("•", r)
