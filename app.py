import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🤖 Adaptive Grid System PRO - Smart Grid Selector (FAST VERSION)")

session = requests.Session()

# =========================
# GET TOP LIQUID COINS (FAST)
# =========================
@st.cache_data(ttl=600)
def get_top_100_coins():
    try:
        url = "https://api.exchange.coinbase.com/products"
        r = session.get(url, timeout=10).json()

        usdt_pairs = []
        for item in r:
            if item["quote_currency"] == "USD":
                usdt_pairs.append(item["id"])

        # نجيب tickers بدل candles (أسرع بكتير)
        volumes = []

        usdt_pairs = usdt_pairs[:100]  # تقليل الضغط

        for symbol in usdt_pairs:
            try:
                url2 = f"https://api.exchange.coinbase.com/products/{symbol}/ticker"
                data = session.get(url2, timeout=5).json()

                if "volume" in data:
                    volume = float(data["volume"])
                    base = symbol.replace("-USD", "")
                    volumes.append((base, volume))
            except:
                pass

        volumes.sort(key=lambda x: x[1], reverse=True)

        return [x[0] for x in volumes[:30]]  # أفضل 30 فقط

    except:
        return []


# =========================
# GET DATA (OPTIMIZED)
# =========================
@st.cache_data(ttl=120)
def get_data(symbol, target_candles=200, granularity=3600):
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
        df = df.sort_values("time", ascending=True).reset_index(drop=True)

        for col in ["low","high","open","close","volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.dropna().tail(target_candles)

    except:
        return None


# =========================
# INDICATORS
# =========================
def add_indicators(df):
    df = df.reset_index(drop=True)

    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-9)
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
# GRID FILTER (STRICT SIDEWAYS)
# =========================
def is_good_for_grid(df):
    latest = df.iloc[-1]

    ema_gap = abs(latest["ema50"] - latest["ema200"]) / latest["close"]
    atr_ratio = latest["atr"] / latest["close"]

    rsi_ok = 40 <= latest["rsi"] <= 60
    not_trending = ema_gap < 0.02
    vol_ok = 0.015 < atr_ratio < 0.04

    return rsi_ok and not_trending and vol_ok


# =========================
# SMART SCORING (IMPROVED)
# =========================
def rank_coin(df):
    latest = df.iloc[-1]

    rsi_score = 30 - abs(50 - latest["rsi"])

    trend_score = 30 - (abs(latest["ema50"] - latest["ema200"]) / latest["close"] * 1000)

    volume_score = 20 if latest["volume"] > latest["vol_ma"] else 5

    atr_score = (latest["atr"] / latest["close"]) * 1000

    return rsi_score + trend_score + volume_score + atr_score


# =========================
# GRID ENGINE
# =========================
def grid_engine(df):
    latest = df.iloc[-1]

    price = latest["close"]
    atr = latest["atr"]

    low = price - atr * 5
    high = price + atr * 5

    volatility = atr / price

    if volatility > 0.035:
        grids = 22
    elif volatility > 0.02:
        grids = 16
    else:
        grids = 10

    return low, high, grids


# =========================
# FIND BEST GRID COIN
# =========================
if st.button("🏆 Find Best GRID Coin (FAST MODE)"):

    coins = get_top_100_coins()
    results = []

    for symbol in coins:
        try:
            df = get_data(symbol, 200)

            if df is None or len(df) < 100:
                continue

            df = add_indicators(df)

            if not is_good_for_grid(df):
                continue

            results.append({
                "Coin": symbol,
                "Score": rank_coin(df)
            })

        except:
            pass

    if results:
        table = pd.DataFrame(results).sort_values("Score", ascending=False)
        st.dataframe(table)

        best = table.iloc[0]["Coin"]
        st.success(f"🔥 Best GRID Coin: {best}")

    else:
        st.warning("No good grid opportunities right now.")


# =========================
# SINGLE ANALYSIS
# =========================
coin = st.text_input("🔎 Enter Coin (e.g BTC, ETH)")

if st.button("Analyze") and coin:
    df = get_data(coin.upper(), 200)

    if df is None or df.empty:
        st.error("No data available")
        st.stop()

    df = add_indicators(df)
    latest = df.iloc[-1]

    if not is_good_for_grid(df):
        st.warning("⚠️ Not ideal for Grid (strong trend detected)")

    low, high, grids = grid_engine(df)

    st.write(f"Price: {latest['close']:.4f}")
    st.write(f"Grid Low: {low:.4f}")
    st.write(f"Grid High: {high:.4f}")
    st.write(f"Grid Levels: {grids}")
    st.write(f"RSI: {latest['rsi']:.2f}")
    st.write(f"ATR: {latest['atr']:.4f}")

    if is_good_for_grid(df):
        st.success("Market Type: SIDEWAYS GRID READY")
    else:
        st.error("Market Type: TRENDING - AVOID GRID")
