import streamlit as st
import pandas as pd
import requests
import datetime
import time

API_KEY = st.secrets["API_KEY"]

st.set_page_config(
    page_title="SPY Flow",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("📱 SPY 0DTE Flow")

if "flow_totals" not in st.session_state:
    st.session_state.flow_totals = {}

if st.sidebar.button("🔄 Reset Premium Totals"):
    st.session_state.flow_totals = {}

def is_0dte(exp):
    today = datetime.date.today()
    exp_date = datetime.datetime.strptime(exp, "%Y-%m-%d").date()
    return exp_date == today

def fetch_data():
    url = "https://api.polygon.io/v3/trades/options"
    params = {
        "underlying_ticker": "SPY",
        "limit": 500,
        "apiKey": API_KEY
    }
    r = requests.get(url, params=params)
    return r.json()

placeholder = st.empty()

while True:
    data = fetch_data()

    for trade in data.get("results", []):
        try:
            if not is_0dte(trade["expiration_date"]):
                continue

            strike = trade["strike_price"]
            typ = trade["contract_type"]
            price = trade["price"]
            size = trade["size"]

            premium = price * size * 100
            key = (strike, typ)

            st.session_state.flow_totals[key] = (
                st.session_state.flow_totals.get(key, 0) + premium
            )

        except:
            continue

    rows = []
    for (strike, typ), premium in st.session_state.flow_totals.items():
        rows.append({
            "Strike": strike,
            "Type": typ,
            "Premium": premium
        })

    df = pd.DataFrame(rows)

    with placeholder.container():
        if df.empty:
            st.info("Waiting for SPY 0DTE flow...")
        else:
            heatmap = df.pivot_table(
                index="Strike",
                columns="Type",
                values="Premium",
                aggfunc="sum",
                fill_value=0
            )

            if "call" not in heatmap.columns:
                heatmap["call"] = 0
            if "put" not in heatmap.columns:
                heatmap["put"] = 0

            heatmap["Total"] = heatmap["call"] + heatmap["put"]
            heatmap["Bias"] = heatmap.apply(
                lambda row: "CALLS 🟢" if row["call"] > row["put"] else "PUTS 🔴",
                axis=1
            )

            heatmap = heatmap.sort_values("Total", ascending=False)

            call_total = heatmap["call"].sum()
            put_total = heatmap["put"].sum()
            total_premium = call_total + put_total

            col1, col2, col3 = st.columns(3)
            col1.metric("Call Premium", f"${call_total:,.0f}")
            col2.metric("Put Premium", f"${put_total:,.0f}")
            col3.metric("Total Flow", f"${total_premium:,.0f}")

            if call_total > put_total:
                st.success("🟢 Calls leading premium flow")
            elif put_total > call_total:
                st.error("🔴 Puts leading premium flow")
            else:
                st.warning("Neutral flow")

            st.subheader("🔥 Premium by Strike")

            st.dataframe(
                heatmap.style
                .format({
                    "call": "${:,.0f}",
                    "put": "${:,.0f}",
                    "Total": "${:,.0f}"
                })
                .background_gradient(cmap="Greens", subset=["call"])
                .background_gradient(cmap="Reds", subset=["put"])
                .background_gradient(cmap="Blues", subset=["Total"]),
                use_container_width=True,
                height=650
            )

    time.sleep(10)
