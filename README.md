# 📈 Ackman-Style Automated Stock Screening Terminal (Seeking Alpha Premium Enhanced)

A Streamlit-based intelligent quantitative analysis terminal that fetches Yahoo Finance fundamentals with one click, performs Ackman-style deep valuation, and integrates advanced features such as Wall Street analyst consensus, five-year financial trend interactive charts, and insider transaction monitoring, creating a local research workstation comparable to Seeking Alpha Premium.

---

## 🚀 Core Features

- **One-Click Smart Fetch**  
  Automatically pulls key data from Yahoo Finance: stock price, forward EPS, net cash per share, PEG ratio, analyst rating, target price, short float, and more.

- **Ackman-Style Dual-Model Valuation**  
  Supports "Profitable Giant Model (Compounding Multiplication)" and "Pre-Profit Growth Model (Absolute Value)", automatically calculating core stock price, 5th-year EPS, 5-year target price, and expected IRR, strictly aligned with the Ackman 15% annualized return threshold.

- **Wall Street Analyst Mirror Panel**  
  Displays consensus rating, average target price, long/short ratio, and the most pessimistic floor price to sense market sentiment in real time.

- **Five-Year Income Trend Interactive Chart (Plotly)**  
  Dual Y-axis dynamic chart: bar chart for revenue, line chart for net income, with hover, zoom, and drag support to review long-term financial trajectory.

- **Insider Transaction Monitoring**  
  Clearly lists trades by CEOs, CFOs, and major shareholders, with purchases highlighted in green (+positive) and sales in red (-negative), warning of insider selling signals.

- **One-Click Excel Export**  
  Export core valuation metrics into a standard financial spreadsheet for archiving or sharing.

---

## 📦 Installation

Ensure Python 3.8 or above is installed, then run:

```bash
# 1. Clone the repository
git clone https://github.com
cd AckmanIndicator-Stock-Analysis

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
streamlit run app.py
```

---

## 🌐 Live Web App

Don't want to install Python locally? Try the fully deployment version directly in your browser:  
👉 **[Launch Live Demo on Streamlit Cloud](https://streamlit.app)**

---

## 🛠️ Tech Stack

- **Frontend/UI**: Streamlit
- **Data Source**: Yahoo Finance API (`yfinance`)
- **Data Visualization**: Plotly (Interactive Charts)
- **Data Export**: Pandas & OpenPyXL (Excel Generator)

---

## 📜 Disclaimer

*This tool is for educational and research purposes only. It does not constitute investment advice, financial advice, trading advice, or any other sort of advice. Please conduct your own due diligence before making any investment decisions.*

pip install streamlit yfinance pandas openpyxl plotly
