import requests
import pandas as pd
import numpy as np

session = requests.Session()


# =========================
# 🟢 COINGECKO - MARKET PICKS
# =========================
def get_market():

    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 30,
        "page": 1,
        "sparkline": False
    }

    r = session.get(url, params=params).json()
    return pd.DataFrame(r)


# =========================
# 🟢 CRYPTOCOMPARE - REAL OHLC
# =========================
def get_ohlc(symbol, tf="hour"):

    url = "https://min-api.cryptocompare.com/data/v2/histohour"

    params = {
        "fsym": symbol.upper(),
        "tsym": "USD",
        "limit": 200
    }

    r = session.get(url, params=params).json()

    if "Data" not in r:
        return None

    data = r["Data"]["Data"]

    df = pd.DataFrame(data)

    return df[["time","open","high","low","close","volumeto"]].rename(
        columns={"volumeto":"volume"}
    )


# =========================
# 📈 INDICATORS
# =========================
def add_indicators(df):

    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    # RSI
    delta = df["close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    rs = pd.Series(gain).ewm(span=14).mean() / (pd.Series(loss).ewm(span=14).mean() + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()

    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9).mean()

    # VWAP
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()

    # Volume MA
    df["vol_ma"] = df["volume"].rolling(20).mean()

    # ATR
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)

    df["atr"] = tr.rolling(14).mean()

    # ADX (simplified)
    df["adx"] = (df["high"] - df["low"]).rolling(14).mean()

    return df.dropna()


# =========================
# ⚙️ MARKET REGIME (4H)
# =========================
def market_regime(df):

    ema50 = df["ema50"].iloc[-1]
    ema200 = df["ema200"].iloc[-1]
    adx = df["adx"].iloc[-1]

    if adx < 18:
        return "SIDEWAYS"

    if ema50 > ema200:
        return "UPTREND"

    if ema50 < ema200:
        return "DOWNTREND"

    return "SIDEWAYS"


# =========================
# 📊 FILTER
# =========================
def filter_quality(df):

    if df["volume"].iloc[-1] < df["volume"].mean():
        return False

    if df["atr"].iloc[-1] / df["close"].iloc[-1] < 0.005:
        return False

    if df["adx"].iloc[-1] < 18:
        return False

    return True


# =========================
# 🎯 ENTRY LOGIC
# =========================
def generate_signal(df_1h, df_4h):

    if not filter_quality(df_1h):
        return None

    regime = market_regime(df_4h)
    latest = df_1h.iloc[-1]

    score = 0
    signal = None

    # =========================
    # 🟢 PULLBACK (BEST)
    # =========================
    if regime == "UPTREND":

        if latest["rsi"] >= 30 and latest["rsi"] <= 45:
            score += 20
            signal = "PULLBACK BUY"

        if latest["close"] <= df_1h["ema50"].iloc[-1] * 1.01:
            score += 10

    # =========================
    # 🔵 BREAKOUT
    # =========================
    resistance = df_1h["high"].rolling(20).max().iloc[-2]

    if latest["close"] > resistance:
        score += 25
        signal = "BREAKOUT BUY"

    # =========================
    # 🟡 MOMENTUM
    # =========================
    if latest["rsi"] > 50:
        score += 10

    if latest["macd"] > df_1h["signal"].iloc[-1]:
        score += 10

    # =========================
    # 📊 CONFIRMATIONS
    # =========================
    if latest["volume"] > df_1h["vol_ma"].iloc[-1]:
        score += 15

    if latest["close"] > df_1h["vwap"].iloc[-1]:
        score += 10

    if latest["adx"] > 18:
        score += 10

    # =========================
    # 📌 DECISION
    # =========================
    if score >= 65:
        return {
            "signal": signal,
            "score": score,
            "regime": regime
        }

    return None


# =========================
# 💰 RISK ENGINE
# =========================
def risk_engine(df):

    entry = df["close"].iloc[-1]
    atr = df["atr"].iloc[-1]

    sl = entry - (1.5 * atr)
    risk = entry - sl

    return {
        "entry": entry,
        "sl": sl,
        "tp1": entry + risk,
        "tp2": entry + (risk * 2),
        "tp3": entry + (risk * 3)
    }


# =========================
# 🚀 SCANNER (1H + 4H)
# =========================
def run_engine():

    market = get_market()

    results = []

    for i in range(min(15, len(market))):

        symbol = market.iloc[i]["symbol"].upper()

        df_1h = get_ohlc(symbol)
        df_4h = get_ohlc(symbol)

        if df_1h is None or df_4h is None:
            continue

        df_1h = add_indicators(df_1h)
        df_4h = add_indicators(df_4h)

        signal = generate_signal(df_1h, df_4h)

        if signal:

            risk = risk_engine(df_1h)

            results.append({
                "Symbol": symbol,
                "Signal": signal["signal"],
                "Score": signal["score"],
                "Regime": signal["regime"],
                "Entry": round(risk["entry"], 4),
                "SL": round(risk["sl"], 4),
                "TP1": round(risk["tp1"], 4),
                "TP2": round(risk["tp2"], 4),
                "TP3": round(risk["tp3"], 4),
            })

    return pd.DataFrame(results)
