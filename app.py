import requests
import pandas as pd
import numpy as np

session = requests.Session()


# =========================
# 🟢 COINGECKO MARKET
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
# 🟢 CRYPTOCOMPARE OHLC
# =========================
def get_ohlc(symbol):

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

    df = df[["time","open","high","low","close","volumeto"]].rename(
        columns={"volumeto": "volume"}
    )

    return df


# =========================
# 📈 INDICATORS
# =========================
def add_indicators(df):

    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    rs = pd.Series(gain).ewm(span=14).mean() / (pd.Series(loss).ewm(span=14).mean() + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()

    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9).mean()

    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()

    df["vol_ma"] = df["volume"].rolling(20).mean()

    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift())
    ], axis=1).max(axis=1)

    df["atr"] = tr.rolling(14).mean()

    return df.dropna()


# =========================
# 🧠 MARKET BIAS (4H logic simplified)
# =========================
def market_bias(df):

    ema50 = df["ema50"].iloc[-1]
    ema200 = df["ema200"].iloc[-1]

    if ema50 > ema200:
        return "UP"
    elif ema50 < ema200:
        return "DOWN"
    return "SIDEWAYS"


# =========================
# 📊 FILTER
# =========================
def filter_quality(df):

    if df["volume"].iloc[-1] < df["volume"].mean():
        return False

    if df["atr"].iloc[-1] / df["close"].iloc[-1] < 0.005:
        return False

    return True


# =========================
# 🎯 SIGNAL ENGINE (BALANCED)
# =========================
def generate_signal(df):

    if not filter_quality(df):
        return None

    bias = market_bias(df)
    latest = df.iloc[-1]

    score = 0
    signal = None

    # 🟢 PULLBACK
    if bias == "UP":

        if 30 <= latest["rsi"] <= 45:
            score += 25
            signal = "PULLBACK BUY"

        if latest["close"] <= df["ema50"].iloc[-1] * 1.01:
            score += 10

    # 🔵 BREAKOUT
    resistance = df["high"].rolling(20).max().iloc[-2]

    if latest["close"] > resistance:
        score += 25
        signal = "BREAKOUT BUY"

    # CONFIRMATIONS
    if latest["macd"] > df["signal"].iloc[-1]:
        score += 10

    if latest["volume"] > df["vol_ma"].iloc[-1]:
        score += 15

    if latest["close"] > df["vwap"].iloc[-1]:
        score += 10

    if score >= 65:
        return {
            "signal": signal,
            "score": score,
            "bias": bias
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
# 🚀 MAIN ENGINE
# =========================
def run_engine():

    market = get_market()

    results = []

    for i in range(min(15, len(market))):

        symbol = market.iloc[i]["symbol"].upper()

        df = get_ohlc(symbol)

        if df is None or len(df) < 120:
            continue

        df = add_indicators(df)

        signal = generate_signal(df)

        if signal:

            risk = risk_engine(df)

            results.append({
                "Symbol": symbol,
                "Signal": signal["signal"],
                "Score": signal["score"],
                "Bias": signal["bias"],
                "Entry": round(risk["entry"], 4),
                "SL": round(risk["sl"], 4),
                "TP1": round(risk["tp1"], 4),
                "TP2": round(risk["tp2"], 4),
                "TP3": round(risk["tp3"], 4),
            })

    return pd.DataFrame(results)
