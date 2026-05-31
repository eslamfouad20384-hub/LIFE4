import streamlit as st
import pandas as pd

from crypto_intraday_engine import run_engine

st.set_page_config(page_title="Crypto Intraday Engine", layout="wide")

st.title("🚀 Crypto Intraday Engine (Hybrid Free Stack)")

st.write("📊 Scanning Market... 1H Intraday Signals")


if st.button("🔥 Run Scan"):

    with st.spinner("Analyzing market..."):

        df = run_engine()

        if df is None or df.empty:
            st.warning("❌ No valid signals found")
        else:
            st.success("🔥 Signals Found")

            st.dataframe(df, use_container_width=True)
