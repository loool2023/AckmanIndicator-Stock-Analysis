import streamlit as st
import pandas as pd
import yfinance as yf
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="阿克曼式智能选股终端", page_icon="📈", layout="wide")
st.title("📈 阿克曼式自动选股雷达系统 （Seeking Alpha Premium 增强版）")
st.markdown("---")

# ==================== 0. 工具函数：拉取并缓存 API 数据 ====================
def fetch_and_cache(ticker):
    """拉取 yfinance 数据并写入 session_state，返回是否成功"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # 核心指标
        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
        eps = info.get("forwardEps") or 0.0

        total_cash = info.get("totalCash") or 0.0
        total_debt = info.get("totalDebt") or 0.0
        shares = info.get("sharesOutstanding") or 1.0
        net_cash = (total_cash - total_debt) / shares

        # PEG 指标
        peg = info.get("forwardPegRatio") or info.get("pegRatio") or None

        # 华尔街共识字段
        rec_key = info.get("recommendationKey", "N/A")
        analyst_count = info.get("numberOfAnalystOpinions", "N/A")
        target_mean = info.get("targetMeanPrice", "N/A")
        target_low = info.get("targetLowPrice", "N/A")
        short_percent = info.get("shortPercentOfFloat", 0.0) * 100

        # 五年损益表历史数据
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

        # 内部人交易数据
        try:
            insider_df = stock.insider_transactions
            if insider_df is None or insider_df.empty:
                insider_df = pd.DataFrame()
            else:
                # 只保留最近 20 条，并重置索引方便展示
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
        st.error(f"❌ API 拉取失败：{e}")
        return False

# ==================== 1. 前端输入与 API 自动化对接 ====================
st.sidebar.header("⚙️ 自动化控制面板")

ticker_input = st.sidebar.text_input("股票代码 (Ticker, 例如 LLY, MSFT, NVTS)", "LLY").upper()

if st.sidebar.button("🔍 智能拉取 API 数据", type="secondary"):
    with st.spinner(f"正在通过 API 拉取 {ticker_input} 的最新财务数据..."):
        if fetch_and_cache(ticker_input):
            st.sidebar.success("✅ 数据同步成功！已自动填入下方表单。")

# 读取缓存或使用默认初始数据
if 'api_data' in st.session_state and st.session_state['api_data']['ticker'] == ticker_input:
    cache = st.session_state['api_data']
    price = st.sidebar.number_input("当前股价 (Share Price, $)", value=cache['price'])
    forward_eps = st.sidebar.number_input("未来12个月预期EPS (Forward EPS, $)", value=cache['eps'])
    net_cash = st.sidebar.number_input("每股净现金 (Net Cash per Share, $)", value=cache['net_cash'])
else:
    price = st.sidebar.number_input("当前股价 (Share Price, $)", value=1015.75)
    forward_eps = st.sidebar.number_input("未来12个月预期EPS (Forward EPS, $)", value=44.26)
    net_cash = st.sidebar.number_input("每股净现金 (Net Cash per Share, $)", value=-19.20)

hidden_asset = st.sidebar.number_input("持股投资每股价值 (Hidden Asset, $)", min_value=0.0, value=0.0)
normal_pe = st.sidebar.number_input("常态化合理市盈率 (Normal P/E)", min_value=0.0, value=30.0)

is_profitable_default = 0 if forward_eps > 0 else 1
is_profitable = st.sidebar.radio(
    "公司当前是否实现稳定盈利？",
    ("已盈利巨头模型（复利乘法流）", "未盈利成长股模型（绝对值流）"),
    index=is_profitable_default
)

if is_profitable == "已盈利巨头模型（复利乘法流）":
    is_prof = True
    cagr_input = st.sidebar.number_input("未来5年EPS复合增速 (5Y EPS CAGR, %)", min_value=0.0, value=16.90, step=0.1)
    cagr_or_future_eps = cagr_input / 100.0
else:
    is_prof = False
    cagr_or_future_eps = st.sidebar.number_input("第5年预期EPS绝对值 ($)", min_value=0.0, value=0.80, step=0.1)

# ==================== 2. 后端核心计算逻辑 ====================
if st.sidebar.button("🚀 点击执行智能估值", type="primary"):
    need_fetch = (
        'api_data' not in st.session_state
        or st.session_state['api_data']['ticker'] != ticker_input
    )
    if need_fetch:
        with st.spinner("检测到尚未拉取分析师数据，正在自动补全..."):
            if not fetch_and_cache(ticker_input):
                st.stop()

    cache = st.session_state['api_data']

    adjusted_core_price = price - net_cash - hidden_asset

    if is_prof:
        model_type = "已盈利巨头模型"
        apparent_pe = f"{price / forward_eps:.2f}x" if forward_eps != 0 else "N/A"
        core_pe_val = adjusted_core_price / forward_eps if forward_eps != 0 else 0
        core_pe = f"{core_pe_val:.2f}x" if forward_eps != 0 else "N/A"
        year_5_eps = forward_eps * ((1 + cagr_or_future_eps) ** 4)
        growth_detail = f"未来5年EPS复合增速预期: {cagr_input:.1f}%"
    else:
        model_type = "未盈利成长股模型"
        apparent_pe = "N/A (当前未盈利)"
        core_pe_val = None
        core_pe = "N/A (当前未盈利)"
        year_5_eps = cagr_or_future_eps
        growth_detail = f"第5年预期EPS绝对值直接设定: ${year_5_eps:.2f}"

    target_price_5y = (year_5_eps * normal_pe) + net_cash + hidden_asset
    irr = (target_price_5y / price) ** (1 / 5) - 1 if target_price_5y > 0 and price > 0 else -1.0

    peg_raw = cache.get('peg')
    peg_display = f"{peg_raw:.2f}x" if peg_raw is not None else "N/A"

    # ==================== 3. 结果渲染可视化 ====================
    st.subheader(f"📊 {ticker_input} 自动化量化诊断报告")
    st.info(f"🧬 **引擎状态：** 系统依据财务基本面智能调取 【{model_type}】 逻辑进行计算。")

    col1, col2, col3 = st.columns(3)
    col1.metric("当前市场股价", f"${price:.2f}")
    col2.metric("表面远期市盈率", apparent_pe)
    col3.metric("核心业务远期市盈率", core_pe)

    col4, col5, col6 = st.columns(3)
    col4.metric("主营实际核心股价", f"${adjusted_core_price:.2f}")
    col5.metric("预测第5年EPS", f"${year_5_eps:.2f}")
    col6.metric("PEG 比率 (前瞻)", peg_display)
    st.markdown(f"*{growth_detail}*")

    st.markdown("---")
    st.subheader("🎯 核心决策指标")
    col7, col8 = st.columns(2)
    col7.metric("🔮 5年后估值修复目标价", f"${target_price_5y:.2f}")

    if irr >= 0.15:
        col8.metric("💰 预期长线年化内部收益率 (IRR)", f"{irr * 100:.2f}%", delta="满足阿克曼门槛 (>=15%)")
        if is_prof and core_pe_val is not None and core_pe_val <= 21.0:
            st.success("🚨 **【核心提示】:** 核心估值极低且IRR达标，完美契合阿克曼标准！")
        else:
            st.success("🚨 **【核心提示】:** 长线回报率成功跑赢 15% 的硬性选股线，具备建仓价值。")
    else:
        col8.metric("💰 预期长线年化内部收益率 (IRR)", f"{irr * 100:.2f}%", delta="-未达阿克曼门槛 (<15%)",
                    delta_color="inverse")
        st.warning("🚨 **【核心提示】:** 估值溢价过高，长线潜在收益有限，建议静待回调。")

    # ==================== 4. 五年损益趋势图 ====================
    st.markdown("---")
    st.subheader("📈 过去五年营收与净利润趋势 (Seeking Alpha 级交互图)")

    income_df = cache.get('income_df', pd.DataFrame())
    if not income_df.empty:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(x=income_df["Year"], y=income_df["Revenue"], name="营收 (Revenue)",
                   marker_color='rgb(55, 128, 191)', opacity=0.7),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=income_df["Year"], y=income_df["NetIncome"], name="净利润 (Net Income)",
                       mode='lines+markers', marker=dict(size=8, color='red'),
                       line=dict(width=3, color='red')),
            secondary_y=True,
        )
        fig.update_layout(
            title=f"{ticker_input} 五年财务爬坡轨迹",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=500
        )
        fig.update_yaxes(title_text="营收（美元）", secondary_y=False)
        fig.update_yaxes(title_text="净利润（美元）", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("暂无足够历史损益数据，可能该股票上市不足五年或数据源缺失。")

    # ==================== 5. 内部人交易监控 (增强版) ====================
    st.markdown("---")
    st.subheader("🕵️ 内部人交易 & 持股变动监控 (CEO/CFO/大股东动向)")

    insider_df = cache.get('insider_df', pd.DataFrame())
    if not insider_df.empty:
        # 统一列名映射（兼容 yfinance 不同版本）
        col_mapping = {
            "Insider": "姓名",
            "Insider Title": "职位",
            "Transaction": "操作",
            "Shares": "股数",
            "Value": "交易金额",
            "Shares Total": "总持股",
            "Start Date": "交易日期"
        }

        # 只保留存在的列
        avail_cols = [col for col in col_mapping if col in insider_df.columns]
        display_df = insider_df[avail_cols].rename(columns={k: v for k, v in col_mapping.items() if k in avail_cols})

        # 处理股数正负号：增持为正，减持为负
        if "操作" in display_df.columns and "股数" in display_df.columns:
            def format_shares(row):
                try:
                    shares = float(row["股数"])
                except (ValueError, TypeError):
                    return row["股数"]
                trade_type = str(row["操作"]).lower()
                if "sale" in trade_type or "sell" in trade_type:
                    return -abs(shares)
                elif "buy" in trade_type or "purchase" in trade_type:
                    return abs(shares)
                else:
                    return shares
            display_df["股数"] = display_df.apply(format_shares, axis=1)

        # 样式：增持绿色，减持红色
        def color_shares(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return 'color: green; font-weight: bold'
                elif val < 0:
                    return 'color: red; font-weight: bold'
            return ''

        # 如果操作列有原始文本，也可着色
        def color_trade(val):
            if isinstance(val, str):
                if "sale" in val.lower() or "sell" in val.lower():
                    return 'color: red; font-weight: bold'
                elif "buy" in val.lower() or "purchase" in val.lower():
                    return 'color: green; font-weight: bold'
            return ''

        styled_df = display_df.style.map(color_shares, subset=['股数'] if '股数' in display_df.columns else [])
        if '操作' in display_df.columns:
            styled_df = styled_df.applymap(color_trade, subset=['操作'])

        st.dataframe(styled_df, use_container_width=True)
        st.caption("数据来源：SEC Form 4。绿色正数 = 增持买入，红色负数 = 减持卖出。")
    else:
        st.info("该股票暂无内部人交易记录，或数据源不支持。")

    # ==================== 6. Excel 导出 ====================
    excel_apparent_pe = f"{price / forward_eps:.2f}" if (is_prof and forward_eps != 0) else "N/A"
    excel_core_pe = f"{adjusted_core_price / forward_eps:.2f}" if (is_prof and forward_eps != 0) else "N/A"

    excel_data = {
        "指标名称 (Financial Metrics)": [
            "当前股价 (Share Price)", "未来12个月预期EPS (Forward EPS)", "表面远期市盈率 (Apparent Forward P/E)",
            "每股净现金 (Net Cash per Share)", "持股投资每股价值 (Hidden Asset Value)",
            "修正后核心企业股价 (Adjusted Core Price)",
            "核心业务远期市盈率 (Core Forward P/E)", "预测第5年每股收益 (Year 5 EPS)",
            "常态化市盈率估值修复 (Normal P/E)",
            "5年后估值修复目标价 (Target Price)", "预期年化内部收益率 (Expected IRR)"
        ],
        "实时抓取与计算结果": [
            price, forward_eps, excel_apparent_pe,
            net_cash, hidden_asset, adjusted_core_price,
            excel_core_pe, year_5_eps, normal_pe,
            target_price_5y, f"{irr * 100:.2f}%"
        ]
    }
    df = pd.DataFrame(excel_data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='阿克曼自动分析表')

    # ==================== 7. Seeking Alpha 风格华尔街共识看板 ====================
    st.markdown("---")
    st.subheader("🎯 华尔街分析师前瞻共识 (Seeking Alpha 镜像面板)")

    rec_key = cache.get('recommendation_key', 'N/A').upper().replace("_", " ")
    analyst_count = cache.get('analyst_count', 'N/A')
    target_mean = cache.get('target_mean', 'N/A')
    target_low = cache.get('target_low', 'N/A')
    short_ratio = cache.get('short_percent', 0.0)

    col_sa1, col_sa2, col_sa3 = st.columns(3)
    col_sa1.metric("华尔街综合评级", f"🔥 {rec_key}",
                   f"共计 {analyst_count} 家投行参与投票" if analyst_count != "N/A" else "")
    col_sa2.metric("分析师平均目标价", f"${target_mean}" if target_mean != "N/A" else "N/A")
    col_sa3.metric("市场多空比例 (空头持仓比)", f"{short_ratio:.2f}%",
                   "大于15%需提防逼空暴涨" if short_ratio > 15 else "多空情绪温和")

    st.markdown(f"⚠️ **安全边际极端压力测试：** 华尔街目前给出的最悲观兜底预测价为 **${target_low}**。")

    st.download_button(
        label="📥 一键导出标准财务 Excel 表格",
        data=buffer.getvalue(),
        file_name=f"Automated_Ackman_Model_{ticker_input}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.write("👈 请在左侧输入 Ticker，先点击 【🔍 智能拉取 API 数据】 进行财务填充，随后点击下方红色的执行按钮。")