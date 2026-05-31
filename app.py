import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 Ultra Smart Coin Analyzer PRO (Single Asset Deep Analysis)")

session = requests.Session()

# =========================
# 📊 MARKET DATA
# =========================
@st.cache_data(ttl=60)
def get_data(symbol):
    try:
        url = f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles?granularity=3600"
        r = session.get(url, timeout=10).json()

        if not isinstance(r, list) or len(r) < 120:
            return None

        df = pd.DataFrame(r, columns=["time","low","high","open","close","volume"])
        df = df.sort_values("time").reset_index(drop=True)

        for col in ["low", "high", "open", "close", "volume"]:
            df[col] = df[col].astype(float)

        return df

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

    avg_gain = pd.Series(gain).ewm(alpha=1/14, adjust=False).mean()
    avg_loss = pd.Series(loss).ewm(alpha=1/14, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9).mean()

    df["vol_ma"] = df["volume"].rolling(20).mean()
    df["support"] = df["low"].rolling(20).min()
    df["resistance"] = df["high"].rolling(20).max()

    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    return df.dropna()


# =========================
# 🧠 ANALYSIS ENGINE
# =========================
def analyze(df):

    latest = df.iloc[-1]

    score = 0
    reasons = []

    # RSI
    if latest["rsi"] < 35:
        score += 15
        reasons.append("RSI منخفض → تشبع بيعي (+15)")
    else:
        reasons.append("RSI مش في منطقة شراء (0)")

    # MACD
    if latest["macd"] > latest["signal"]:
        score += 15
        reasons.append("MACD إيجابي (+15)")
    else:
        reasons.append("MACD سلبي (0)")

    # Trend EMA
    if latest["ema50"] > latest["ema200"]:
        score += 15
        reasons.append("ترند صاعد EMA50 > EMA200 (+15)")
    else:
        reasons.append("ترند هابط أو ضعيف (0)")

    # Support proximity
    if latest["close"] <= latest["support"] * 1.02:
        score += 10
        reasons.append("السعر قريب من الدعم (+10)")
    else:
        reasons.append("بعيد عن الدعم (0)")

    # Volume
    if latest["volume"] > latest["vol_ma"]:
        score += 10
        reasons.append("حجم تداول قوي (+10)")
    else:
        reasons.append("حجم ضعيف (0)")

    # ATR strength
    if latest["atr"] > df["atr"].mean():
        score += 10
        reasons.append("تقلب جيد ATR (+10)")
    else:
        reasons.append("حركة ضعيفة (0)")

    # Momentum
    if latest["close"] > df["close"].iloc[-5:].mean():
        score += 10
        reasons.append("زخم صاعد (+10)")
    else:
        reasons.append("زخم ضعيف (0)")

    # Trend strength
    if df["close"].iloc[-10:].mean() > df["close"].iloc[-30:-10].mean():
        score += 5
        reasons.append("اتجاه قصير المدى صاعد (+5)")
    else:
        reasons.append("اتجاه ضعيف (0)")

    signal = (
        "🔥 قوي جدًا" if score >= 80 else
        "🟢 فرصة" if score >= 65 else
        "⚠️ مراقبة" if score >= 50 else
        "❌ ضعيف"
    )

    return score, signal, reasons


# =========================
# 🛑 RISK MANAGEMENT
# =========================
def risk_management(df):

    latest = df.iloc[-1]
    entry = latest["close"]
    atr = latest["atr"]
    resistance = latest["resistance"]

    sl = entry - (1.5 * atr)
    risk = entry - sl

    tp1 = entry + risk
    tp2 = entry + (risk * 2)
    tp3 = max(resistance, tp2)

    return entry, sl, tp1, tp2, tp3


# =========================
# 🚀 UI INPUT
# =========================
coin = st.text_input("🔎 اكتب اسم العملة (مثال: BTC, ETH, SOL)")

if st.button("🚀 Analyze Coin") and coin:

    df = get_data(coin.upper())

    if df is None:
        st.error("❌ مفيش بيانات للعملة دي")
        st.stop()

    df = add_indicators(df)

    score, signal, reasons = analyze(df)
    entry, sl, tp1, tp2, tp3 = risk_management(df)

    latest = df.iloc[-1]

    # =========================
    # 📊 SUMMARY TABLE
    # =========================
    st.subheader("📊 Market Data")
    st.dataframe(pd.DataFrame({
        "Price": [latest["close"]],
        "RSI": [latest["rsi"]],
        "MACD": [latest["macd"]],
        "Signal": [latest["signal"]],
        "EMA50": [latest["ema50"]],
        "EMA200": [latest["ema200"]],
        "ATR": [latest["atr"]],
        "Support": [latest["support"]],
        "Resistance": [latest["resistance"]],
        "Volume": [latest["volume"]],
    }), use_container_width=True)

    # =========================
    # 🎯 RESULTS TABLE
    # =========================
    st.subheader("🎯 Trading Plan")
    st.dataframe(pd.DataFrame({
        "Entry": [entry],
        "Stop Loss": [sl],
        "TP1": [tp1],
        "TP2": [tp2],
        "TP3": [tp3],
        "Score": [score],
        "Signal": [signal],
    }), use_container_width=True)

    # =========================
    # 🧠 REASONS
    # =========================
    st.subheader("🧠 Why this score?")
    for r in reasons:
        st.write("•", r)
