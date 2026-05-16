import streamlit as st
import pandas as pd
import yfinance as yf
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Ackman-Style Stock Screener", page_icon="📈", layout="wide")
st.title("📈 Ackman-Style Automated Stock Screener (Seeking Alpha Premium Enhanced)")
st.markdown("---")

# ==================== 0. Utility: Fetch & Cache API Data ====================
def fetch_and_cache(ticker):
    """Fetch yfinance data and store in session_state. Returns True on success."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Core metrics
        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
        eps = info.get("forwardEps") or 0.0

        total_cash = info.get("totalCash") or 0.0
        total_debt = info.get("totalDebt") or 0.0
        shares = info.get("sharesOutstanding") or 1.0
        net_cash = (total_cash - total_debt) / shares

        # PEG ratio
        peg = info.get("forwardPegRatio") or info.get("pegRatio") or None

        # Wall Street consensus fields
        rec_key = info.get("recommendationKey", "N/A")
        analyst_count = info.get("numberOfAnalystOpinions", "N/A")
        target_mean = info.get("targetMeanPrice", "N/A")
        target_low = info.get("targetLowPrice", "N/A")
        short_percent = info.get("shortPercentOfFloat", 0.0) * 100

        # 5-Year income statement history
        try:
            income_stmt = stock.financials.T
            income_stmt = income_stmt.sort_index(ascending=True).tail(5)
            revenue = income_stmt.get("Total Revenue", pd.Series(dtype=float))
            net_income = income_stmt.get("Net Income", pd.Series(dtype=float))
            df_income = pd.DataFrame({
                "Year": [str(d.year) for d in revenue.index],
                "Revenue": revenue.values,
                "NetIncome": net_income.values
            }).dropna(subset=["Revenue", "NetIncome"])
        except Exception:
            df_income = pd.DataFrame()

        # Insider transactions
        try:
            insider_df = stock.insider_transactions
            if insider_df is None or insider_df.empty:
                insider_df = pd.DataFrame()
            else:
                insider_df = insider_df.head(20).reset_index(drop=True)
        except Exception:
            insider_df = pd.DataFrame()

        st.session_state['api_data'] = {
            'price': price,
            'eps': eps,
            'net_cash': net_cash,
            'ticker': ticker,
            'peg': peg,
            'recommendation_key': rec_key,
            'analyst_count': analyst_count,
            'target_mean': target_mean,
            'target_low': target_low,
            'short_percent': short_percent,
            'income_df': df_income,
            'insider_df': insider_df
        }
        return True
    except Exception as e:
        st.error(f"❌ API fetch failed: {e}")
        return False

# ==================== 1. Sidebar Inputs & API Integration ====================
st.sidebar.header("⚙️ Automated Control Panel")

ticker_input = st.sidebar.text_input("Stock Ticker (e.g., LLY, MSFT, NVTS)", "LLY").upper()

if st.sidebar.button("🔍 Smart Fetch API Data", type="secondary"):
    with st.spinner(f"Fetching latest financials for {ticker_input}..."):
        if fetch_and_cache(ticker_input):
            st.sidebar.success("✅ Data synced successfully! Auto-filled form below.")

# Read from cache or use defaults
if 'api_data' in st.session_state and st.session_state['api_data']['ticker'] == ticker_input:
    cache = st.session_state['api_data']
    price = st.sidebar.number_input("Current Share Price ($)", value=cache['price'])
    forward_eps = st.sidebar.number_input("Forward EPS (12M) ($)", value=cache['eps'])
    net_cash = st.sidebar.number_input("Net Cash per Share ($)", value=cache['net_cash'])
else:
    price = st.sidebar.number_input("Current Share Price ($)", value=1015.75)
    forward_eps = st.sidebar.number_input("Forward EPS (12M) ($)", value=44.26)
    net_cash = st.sidebar.number_input("Net Cash per Share ($)", value=-19.20)

hidden_asset = st.sidebar.number_input("Hidden Asset Value per Share ($)", min_value=0.0, value=0.0)
normal_pe = st.sidebar.number_input("Normalized P/E Ratio", min_value=0.0, value=30.0)

is_profitable_default = 0 if forward_eps > 0 else 1
is_profitable = st.sidebar.radio(
    "Is the company currently profitable?",
    ("Profitable Giant (Compounding Model)", "Pre-Profit Growth (Absolute Value Model)"),
    index=is_profitable_default
)

if is_profitable == "Profitable Giant (Compounding Model)":
    is_prof = True
    cagr_input = st.sidebar.number_input("5-Year EPS CAGR (%)", min_value=0.0, value=16.90, step=0.1)
    cagr_or_future_eps = cagr_input / 100.0
else:
    is_prof = False
    cagr_or_future_eps = st.sidebar.number_input("5th Year EPS Estimate ($)", min_value=0.0, value=0.80, step=0.1)

# ==================== 2. Core Valuation Logic ====================
if st.sidebar.button("🚀 Execute Smart Valuation", type="primary"):
    # Auto-fetch if cache is missing or ticker changed
    need_fetch = (
        'api_data' not in st.session_state
        or st.session_state['api_data']['ticker'] != ticker_input
    )
    if need_fetch:
        with st.spinner("No data cached. Auto-fetching analyst data..."):
            if not fetch_and_cache(ticker_input):
                st.stop()

    cache = st.session_state['api_data']

    adjusted_core_price = price - net_cash - hidden_asset

    if is_prof:
        model_type = "Profitable Giant (Compounding)"
        apparent_pe = f"{price / forward_eps:.2f}x" if forward_eps != 0 else "N/A"
        core_pe_val = adjusted_core_price / forward_eps if forward_eps != 0 else 0
        core_pe = f"{core_pe_val:.2f}x" if forward_eps != 0 else "N/A"
        year_5_eps = forward_eps * ((1 + cagr_or_future_eps) ** 4)
        growth_detail = f"5-Year EPS CAGR Estimate: {cagr_input:.1f}%"
    else:
        model_type = "Pre-Profit Growth (Absolute Value)"
        apparent_pe = "N/A (Currently Unprofitable)"
        core_pe_val = None
        core_pe = "N/A (Currently Unprofitable)"
        year_5_eps = cagr_or_future_eps
        growth_detail = f"5th Year EPS Absolute Estimate: ${year_5_eps:.2f}"

    target_price_5y = (year_5_eps * normal_pe) + net_cash + hidden_asset
    irr = (target_price_5y / price) ** (1 / 5) - 1 if target_price_5y > 0 and price > 0 else -1.0

    peg_raw = cache.get('peg')
    peg_display = f"{peg_raw:.2f}x" if peg_raw is not None else "N/A"

    # ==================== 3. Results Visualization ====================
    st.subheader(f"📊 {ticker_input} Automated Quantitative Diagnosis Report")
    st.info(f"🧬 **Engine Status:** System intelligently selected the **{model_type}** logic based on fundamentals.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Current Market Price", f"${price:.2f}")
    col2.metric("Apparent Forward P/E", apparent_pe)
    col3.metric("Core Business Forward P/E", core_pe)

    col4, col5, col6 = st.columns(3)
    col4.metric("Adjusted Core Price", f"${adjusted_core_price:.2f}")
    col5.metric("Projected 5th Year EPS", f"${year_5_eps:.2f}")
    col6.metric("PEG Ratio (Forward)", peg_display)
    st.markdown(f"*{growth_detail}*")

    st.markdown("---")
    st.subheader("🎯 Key Decision Metrics")
    col7, col8 = st.columns(2)
    col7.metric("🔮 5-Year Target Price (Recovery)", f"${target_price_5y:.2f}")

    if irr >= 0.15:
        col8.metric("💰 Expected Long-Term IRR", f"{irr * 100:.2f}%", delta="Meets Ackman Threshold (>=15%)")
        if is_prof and core_pe_val is not None and core_pe_val <= 21.0:
            st.success("🚨 **Core Insight:** Extremely low core valuation with IRR meeting threshold. Perfect Ackman criteria!")
        else:
            st.success("🚨 **Core Insight:** Long-term return exceeds 15% hurdle rate, suitable for position building.")
    else:
        col8.metric("💰 Expected Long-Term IRR", f"{irr * 100:.2f}%", delta="Below Ackman Threshold (<15%)",
                    delta_color="inverse")
        st.warning("🚨 **Core Insight:** Overvalued, limited long-term potential. Consider waiting for a pullback.")

    # ==================== 4. 5-Year Income Trend Interactive Chart ====================
    st.markdown("---")
    st.subheader("📈 5-Year Revenue & Net Income Trend (Seeking Alpha-Grade Interactive Chart)")

    income_df = cache.get('income_df', pd.DataFrame())
    if not income_df.empty:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(x=income_df["Year"], y=income_df["Revenue"], name="Revenue",
                   marker_color='rgb(55, 128, 191)', opacity=0.7),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=income_df["Year"], y=income_df["NetIncome"], name="Net Income",
                       mode='lines+markers', marker=dict(size=8, color='red'),
                       line=dict(width=3, color='red')),
            secondary_y=True,
        )
        fig.update_layout(
            title=f"{ticker_input} 5-Year Financial Trajectory",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=500
        )
        fig.update_yaxes(title_text="Revenue (USD)", secondary_y=False)
        fig.update_yaxes(title_text="Net Income (USD)", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient historical income data. The stock may have been listed less than 5 years or data is unavailable.")

    # ==================== 5. Insider Trading Monitoring (Enhanced) ====================
    st.markdown("---")
    st.subheader("🕵️ Insider Trading & Ownership Changes (CEO/CFO/Major Shareholders)")

    insider_df = cache.get('insider_df', pd.DataFrame())
    if not insider_df.empty:
        # Map original columns to readable English names
        col_mapping = {
            "Insider": "Name",
            "Insider Title": "Title",
            "Transaction": "Transaction",
            "Shares": "Shares",
            "Value": "Value",
            "Shares Total": "Total Shares",
            "Start Date": "Date"
        }

        avail_cols = [col for col in col_mapping if col in insider_df.columns]
        display_df = insider_df[avail_cols].rename(columns={k: v for k, v in col_mapping.items() if k in avail_cols})

        # Format Shares: positive for buys, negative for sells
        if "Transaction" in display_df.columns and "Shares" in display_df.columns:
            def format_shares(row):
                try:
                    shares = float(row["Shares"])
                except (ValueError, TypeError):
                    return row["Shares"]
                trade_type = str(row["Transaction"]).lower()
                if "sale" in trade_type or "sell" in trade_type:
                    return -abs(shares)
                elif "buy" in trade_type or "purchase" in trade_type:
                    return abs(shares)
                else:
                    return shares
            display_df["Shares"] = display_df.apply(format_shares, axis=1)

        # Style: green for positive, red for negative
        def color_shares(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return 'color: green; font-weight: bold'
                elif val < 0:
                    return 'color: red; font-weight: bold'
            return ''

        def color_trade(val):
            if isinstance(val, str):
                if "sale" in val.lower() or "sell" in val.lower():
                    return 'color: red; font-weight: bold'
                elif "buy" in val.lower() or "purchase" in val.lower():
                    return 'color: green; font-weight: bold'
            return ''

        styled_df = display_df.style.map(color_shares, subset=['Shares'] if 'Shares' in display_df.columns else [])
        if 'Transaction' in display_df.columns:
            styled_df = styled_df.map(color_trade, subset=['Transaction'])

        st.dataframe(styled_df, use_container_width=True)
        st.caption("Source: SEC Form 4. Green positive = Buy, Red negative = Sell.")
    else:
        st.info("No insider transactions available for this stock.")

    # ==================== 6. Excel Export ====================
    excel_apparent_pe = f"{price / forward_eps:.2f}" if (is_prof and forward_eps != 0) else "N/A"
    excel_core_pe = f"{adjusted_core_price / forward_eps:.2f}" if (is_prof and forward_eps != 0) else "N/A"

    excel_data = {
        "Metric": [
            "Share Price",
            "Forward EPS (12M)",
            "Apparent Forward P/E",
            "Net Cash per Share",
            "Hidden Asset Value per Share",
            "Adjusted Core Price",
            "Core Forward P/E",
            "Projected Year 5 EPS",
            "Normalized P/E",
            "5-Year Target Price",
            "Expected IRR"
        ],
        "Value": [
            price,
            forward_eps,
            excel_apparent_pe,
            net_cash,
            hidden_asset,
            adjusted_core_price,
            excel_core_pe,
            year_5_eps,
            normal_pe,
            target_price_5y,
            f"{irr * 100:.2f}%"
        ]
    }
    df = pd.DataFrame(excel_data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Ackman Automated Analysis')

    # ==================== 7. Wall Street Analyst Consensus Panel ====================
    st.markdown("---")
    st.subheader("🎯 Wall Street Analyst Consensus (Seeking Alpha Mirror Panel)")

    rec_key = cache.get('recommendation_key', 'N/A').upper().replace("_", " ")
    analyst_count = cache.get('analyst_count', 'N/A')
    target_mean = cache.get('target_mean', 'N/A')
    target_low = cache.get('target_low', 'N/A')
    short_ratio = cache.get('short_percent', 0.0)

    col_sa1, col_sa2, col_sa3 = st.columns(3)
    col_sa1.metric("Consensus Rating", f"🔥 {rec_key}",
                   f"Based on {analyst_count} analyst ratings" if analyst_count != "N/A" else "")
    col_sa2.metric("Average Analyst Target", f"${target_mean}" if target_mean != "N/A" else "N/A")
    col_sa3.metric("Short Float Ratio", f"{short_ratio:.2f}%",
                   ">15%: Watch for short squeeze risk" if short_ratio > 15 else "Sentiment moderate")

    st.markdown(f"⚠️ **Margin of Safety Stress Test:** Wall Street's most pessimistic target is **${target_low}**.")

    st.download_button(
        label="📥 Export Standard Financial Excel",
        data=buffer.getvalue(),
        file_name=f"Ackman_Valuation_{ticker_input}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.write("👈 Enter a ticker on the left. Click [🔍 Smart Fetch API Data] to populate financials, then click the red execute button below.")