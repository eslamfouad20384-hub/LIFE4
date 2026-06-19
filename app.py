import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🤖 Adaptive Grid System PRO (V2 Improved)")

session = requests.Session()

# =========================
# 📊 DATA
# =========================
@st.cache_data(ttl=120)
def get_data(symbol, target_candles=600, granularity=3600):

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
# 📈 INDICATORS (FIXED RSI)
# =========================
def add_indicators(df):

    df = df.reset_index(drop=True)

    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()

    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    df["vol_ma"] = df["volume"].rolling(20).mean()

    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)

    df["atr"] = tr.rolling(14).mean()

    return df.dropna().reset_index(drop=True)


# =========================
# 🧠 MARKET REGIME FILTER (NEW)
# =========================
def market_regime(df):

    atr_ratio = df["atr"].iloc[-1] / df["close"].iloc[-1]

    ema_diff = abs(df["ema50"].iloc[-1] - df["ema200"].iloc[-1]) / df["close"].iloc[-1]

    if atr_ratio > 0.04:
        return "HIGH_VOL"
    elif ema_diff > 0.05:
        return "TRENDING"
    elif atr_ratio < 0.015:
        return "LOW_VOL"
    else:
        return "RANGING"


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
# 🔥 IMPROVED SUPPORT/RESISTANCE
# =========================
def detect_levels(df):

    highs = df["high"].values
    lows = df["low"].values

    pivot_highs = []
    pivot_lows = []

    for i in range(5, len(df) - 5):

        if all(highs[i] > highs[i-j] for j in range(1, 6)) and \
           all(highs[i] > highs[i+j] for j in range(1, 6)):
            pivot_highs.append(highs[i])

        if all(lows[i] < lows[i-j] for j in range(1, 6)) and \
           all(lows[i] < lows[i+j] for j in range(1, 6)):
            pivot_lows.append(lows[i])

    # fallback protection
    support = (
        np.mean(pivot_lows[-3:]) if len(pivot_lows) >= 3
        else df["low"].rolling(50).min().iloc[-1]
    )

    resistance = (
        np.mean(pivot_highs[-3:]) if len(pivot_highs) >= 3
        else df["high"].rolling(50).max().iloc[-1]
    )

    return support, resistance


# =========================
# 🔥 IMPROVED RANGE CALCULATION
# =========================
def calc_range(price, support, resistance, atr):

    base_low = min(support, price - atr * 3)
    base_high = max(resistance, price + atr * 3)

    # prevent too small range
    min_range = price * 0.03

    if (base_high - base_low) < min_range:
        base_low = price - min_range
        base_high = price + min_range

    return base_low, base_high


# =========================
# 🤖 GRID ENGINE
# =========================
def grid_engine(df, score):

    latest = df.iloc[-1]
    price = latest["close"]
    atr = latest["atr"]

    support, resistance = detect_levels(df)
    low, high = calc_range(price, support, resistance, atr)

    regime = market_regime(df)

    # grid logic based on regime + score
    if regime == "HIGH_VOL":
        grids = 20
    elif regime == "TRENDING":
        grids = 10 if score < 60 else 15
    elif regime == "LOW_VOL":
        grids = 40
    else:  # RANGING
        grids = 30 if score > 55 else 20

    return low, high, grids, regime


# =========================
# 🚀 UI
# =========================
coin = st.text_input("🔎 Enter Coin (BTC, ETH, SOL...)")

if st.button("Analyze") and coin:

    df = get_data(coin.upper(), 600)

    if df is None or df.empty:
        st.error("No data")
        st.stop()

    df = add_indicators(df)

    score, reasons = analyze(df)

    low, high, grids, regime = grid_engine(df, score)

    st.subheader("🤖 Market Regime")
    st.write(regime)

    st.subheader("📊 Grid Setup")
    st.write(f"Low: {low:.6f}")
    st.write(f"High: {high:.6f}")
    st.write(f"Grids: {grids}")

    st.subheader("🧠 Score")
    st.write(score)

    st.subheader("📌 Reasons")
    for r in reasons:
        st.write("•", r)
