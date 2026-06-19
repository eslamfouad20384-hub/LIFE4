import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🤖 Adaptive Grid System PRO - Smart Grid Selector")

session = requests.Session()

# =========================
# GET TOP 100 COINS (LIQUIDITY)
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

        volumes = []

        for symbol in usdt_pairs[:150]:
            try:
                url2 = f"https://api.exchange.coinbase.com/products/{symbol}/candles"
                data = session.get(url2, params={"granularity": 3600}, timeout=5).json()

                if isinstance(data, list) and len(data) > 0:
                    volume = sum([x[5] for x in data[:20]])
                    base = symbol.replace("-USD", "")
                    volumes.append((base, volume))
            except:
                pass

        volumes.sort(key=lambda x: x[1], reverse=True)

        return [x[0] for x in volumes[:100]]

    except:
        return []


# =========================
# GET DATA (COINBASE)
# =========================
@st.cache_data(ttl=120)
def get_data(symbol, target_candles=500, granularity=3600):
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
# GRID FILTER (SIDEWAYS ONLY)
# =========================
def is_good_for_grid(df):
    latest = df.iloc[-1]

    # 1) Trend strength (ADX-like proxy using EMA distance)
    ema_gap = abs(latest["ema50"] - latest["ema200"]) / latest["close"]

    # 2) Volatility stability
    atr_ratio = latest["atr"] / latest["close"]

    # 3) RSI not extreme trend zone
    rsi_ok = 35 <= latest["rsi"] <= 65

    # 4) No strong trend
    not_trending = ema_gap < 0.03

    # 5) volatility must exist but not explode
    vol_ok = 0.01 < atr_ratio < 0.06

    return rsi_ok and not_trending and vol_ok


# =========================
# SCORING
# =========================
def rank_coin(df):
    latest = df.iloc[-1]

    score = 0

    # Grid-friendly bias
    if 40 <= latest["rsi"] <= 60:
        score += 25

    if abs(latest["macd"] - latest["signal"]) < 0.0005:
        score += 20

    if latest["volume"] > latest["vol_ma"]:
        score += 15

    # sideways confirmation
    if abs(latest["ema50"] - latest["ema200"]) / latest["close"] < 0.02:
        score += 25

    if latest["atr"] / latest["close"] > 0.015:
        score += 15

    return score


# =========================
# GRID ENGINE
# =========================
def grid_engine(df):
    latest = df.iloc[-1]

    price = latest["close"]
    atr = latest["atr"]

    low = price - atr * 6
    high = price + atr * 6

    volatility = atr / price

    if volatility > 0.04:
        grids = 25
    elif volatility > 0.025:
        grids = 18
    else:
        grids = 12

    return low, high, grids


# =========================
# FIND BEST GRID COIN
# =========================
if st.button("🏆 Find Best GRID Coin (Sideways Only)"):

    coins = get_top_100_coins()
    results = []

    for symbol in coins:
        try:
            df = get_data(symbol, 400)

            if df is None or len(df) < 120:
                continue

            df = add_indicators(df)

            # FILTER: ONLY SIDEWAYS MARKET
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
        st.success(f"🔥 Best GRID Coin (Sideways Market): {best}")
    else:
        st.warning("No good grid opportunities right now.")


# =========================
# SINGLE ANALYSIS
# =========================
coin = st.text_input("🔎 Enter Coin")

if st.button("Analyze") and coin:
    df = get_data(coin.upper(), 500)

    if df is None or df.empty:
        st.error("No data")
        st.stop()

    df = add_indicators(df)

    latest = df.iloc[-1]

    if not is_good_for_grid(df):
        st.warning("⚠️ Not ideal for Grid (strong trend detected)")

    low, high, grids = grid_engine(df)

    st.write(f"Price: {latest['close']:.4f}")
    st.write(f"Low: {low:.4f}")
    st.write(f"High: {high:.4f}")
    st.write(f"Grids: {grids}")
    st.write(f"RSI: {latest['rsi']:.2f}")
    st.write(f"ATR: {latest['atr']:.4f}")

    st.write("Market Type: SIDEWAYS GRID READY" if is_good_for_grid(df) else "TREND MARKET (avoid grid)")
