import streamlit as st
import pandas as pd
import requests
import datetime
import time

API_KEY = st.secrets["API_KEY"]

st.set_page_config(
    page_title="SPY 0DTE Flow",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("📱 SPY 0DTE Flow Tracker")

if "last_premium" not in st.session_state:
    st.session_state.last_premium = {}

if "flow_totals" not in st.session_state:
    st.session_state.flow_totals = {}

if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = str(datetime.date.today())

# Auto reset each new day
today_str = str(datetime.date.today())
if st.session_state.last_reset_date != today_str:
    st.session_state.flow_totals = {}
    st.session_state.last_premium = {}
    st.session_state.last_reset_date = today_str

st.sidebar.header("Settings")

refresh_seconds = st.sidebar.slider(
    "Refresh seconds",
    min_value=10,
    max_value=60,
    value=15,
    step=5
)

strike_range = st.sidebar.slider(
    "Strike range around hottest strike",
    min_value=2,
    max_value=30,
    value=10,
    step=1
)

sort_mode = st.sidebar.selectbox(
    "Sort list by",
    ["Hottest Premium", "Strike Price"]
)

if st.sidebar.button("🔄 Reset Premium Totals"):
    st.session_state.flow_totals = {}
    st.session_state.last_premium = {}

def fetch_data():
    url = "https://api.polygon.io/v3/snapshot/options/SPY"

    params = {
        "apiKey": API_KEY,
        "limit": 250
    }

    r = requests.get(url, params=params)

    st.sidebar.write("API Status:", r.status_code)
    st.sidebar.write("API Preview:", r.text[:250])

    try:
        return r.json()
    except Exception:
        return {}

def get_option_premium(option):
    details = option.get("details", {})
    day = option.get("day", {})
    last_trade = option.get("last_trade", {})

    strike = details.get("strike_price")
    typ = details.get("contract_type")
    exp = details.get("expiration_date")

    if exp != str(datetime.date.today()):
        return None

    last_price = 0
    volume = 0

    if isinstance(last_trade, dict):
        last_price = last_trade.get("price", 0) or 0

    if isinstance(day, dict):
        volume = day.get("volume", 0) or 0

    estimated_premium = last_price * volume * 100

    return strike, typ, estimated_premium, volume, last_price

placeholder = st.empty()

while True:
    data = fetch_data()
    results = data.get("results", [])

    for option in results:
        try:
            parsed = get_option_premium(option)

            if parsed is None:
                continue

            strike, typ, estimated_premium, volume, last_price = parsed

            if strike is None or typ is None:
                continue

            key = (strike, typ)

            previous_premium = st.session_state.last_premium.get(key, 0)
            premium_change = max(estimated_premium - previous_premium, 0)

            st.session_state.last_premium[key] = estimated_premium
            st.session_state.flow_totals[key] = (
                st.session_state.flow_totals.get(key, 0) + premium_change
            )

        except Exception:
            continue

    rows = []
    for (strike, typ), premium in st.session_state.flow_totals.items():
        rows.append({
            "Strike": strike,
            "Type": typ,
            "Accumulated Premium": premium
        })

    df = pd.DataFrame(rows)

    with placeholder.container():
        if df.empty:
            st.info("Waiting for SPY 0DTE snapshot data...")
        else:
            heatmap = df.pivot_table(
                index="Strike",
                columns="Type",
                values="Accumulated Premium",
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

            heatmap = heatmap[heatmap["Total"] > 0]

            if heatmap.empty:
                st.info("Waiting for premium changes...")
            else:
                hottest_strike = heatmap["Total"].idxmax()

                low_strike = hottest_strike - strike_range
                high_strike = hottest_strike + strike_range

                range_df = heatmap[
                    (heatmap.index >= low_strike) &
                    (heatmap.index <= high_strike)
                ].copy()

                call_total = heatmap["call"].sum()
                put_total = heatmap["put"].sum()
                total_premium = call_total + put_total

                col1, col2, col3 = st.columns(3)
                col1.metric("Call Premium", f"${call_total:,.0f}")
                col2.metric("Put Premium", f"${put_total:,.0f}")
                col3.metric("Total Flow", f"${total_premium:,.0f}")

                if call_total > put_total:
                    st.success("🟢 Calls leading estimated premium flow")
                elif put_total > call_total:
                    st.error("🔴 Puts leading estimated premium flow")
                else:
                    st.warning("Neutral flow")

                st.subheader("👑 Dominant Strikes")

                top_df = heatmap.sort_values("Total", ascending=False).head(5)

                for strike, row in top_df.iterrows():
                    st.markdown(
                        f"""
                        <div style="
                            padding:12px;
                            margin-bottom:8px;
                            border-radius:14px;
                            background:#111827;
                            color:white;
                            border:1px solid #374151;">
                            <b>Strike {strike}</b> — {row['Bias']}<br>
                            Calls: ${row['call']:,.0f} |
                            Puts: ${row['put']:,.0f} |
                            Total: ${row['Total']:,.0f}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                st.subheader("🔥 Block Heat Map")

                max_premium = range_df["Total"].max()

                for strike, row in range_df.sort_index(ascending=False).iterrows():
                    call_intensity = int((row["call"] / max_premium) * 220) if max_premium > 0 else 0
                    put_intensity = int((row["put"] / max_premium) * 220) if max_premium > 0 else 0

                    st.markdown(
                        f"""
                        <div style="display:flex; gap:8px; margin-bottom:8px;">
                            <div style="
                                flex:1;
                                padding:14px;
                                border-radius:12px;
                                background:rgba(0,{call_intensity},90,0.95);
                                color:white;
                                text-align:center;
                                font-weight:700;">
                                CALL<br>{strike}<br>${row['call']:,.0f}
                            </div>

                            <div style="
                                width:72px;
                                padding:14px;
                                border-radius:12px;
                                background:#020617;
                                color:white;
                                text-align:center;
                                font-weight:900;">
                                {strike}
                            </div>

                            <div style="
                                flex:1;
                                padding:14px;
                                border-radius:12px;
                                background:rgba({put_intensity},0,60,0.95);
                                color:white;
                                text-align:center;
                                font-weight:700;">
                                PUT<br>{strike}<br>${row['put']:,.0f}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                st.subheader("📋 Strike Premium List")

                list_df = range_df.copy()

                if sort_mode == "Hottest Premium":
                    list_df = list_df.sort_values("Total", ascending=False)
                else:
                    list_df = list_df.sort_index(ascending=True)

                st.dataframe(
                    list_df.style
                    .format({
                        "call": "${:,.0f}",
                        "put": "${:,.0f}",
                        "Total": "${:,.0f}"
                    })
                    .background_gradient(cmap="Greens", subset=["call"])
                    .background_gradient(cmap="Reds", subset=["put"])
                    .background_gradient(cmap="Blues", subset=["Total"]),
                    use_container_width=True,
                    height=500
                )

    time.sleep(refresh_seconds)
