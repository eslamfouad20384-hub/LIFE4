import streamlit as st
from crypto_intraday_engine import run_engine

st.set_page_config(page_title="Crypto Engine", layout="wide")

st.title("🚀 Crypto Intraday Engine (Stable Version)")

st.write("Scanning market using CoinGecko + CryptoCompare OHLC")

if st.button("🔥 Run Scan"):

    with st.spinner("Working..."):

        df = run_engine()

        if df is None or df.empty:
            st.warning("❌ No valid signals found")
        else:
            st.success("🔥 Signals Found")
            st.dataframe(df, use_container_width=True)
