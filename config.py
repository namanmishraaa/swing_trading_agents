"""
All the knobs you're likely to want to change live here.
Nothing in this file talks to the network — it's just settings.
"""

# --- Universe: which NSE tickers to scan ---
# yfinance expects the ".NS" suffix for NSE-listed stocks.
WATCHLIST = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "LT.NS",
    "SBIN.NS",
    "AXISBANK.NS",
    "BHARTIARTL.NS",
    "ITC.NS",
]

# --- Money & risk (Commander uses these) ---
CAPITAL = 100_000          # total trading capital in INR — set this to your own
RISK_PER_TRADE_PCT = 1.0   # % of capital you're willing to lose if a stop is hit
MAX_POSITIONS = 5          # Commander stops opening new trades after this many
MIN_CONFIDENCE = 65        # Predictor score (0-100) below this is auto-skipped

# --- Predictor: optional LLM-backed reasoning ---
# False = pure rule-based scoring, no API key needed, runs instantly.
# True  = also asks Claude for a one-line qualitative read on the setup
#         (needs ANTHROPIC_API_KEY in .env).
USE_LLM_REASONING = False
LLM_MODEL = "claude-haiku-4-5-20251001"  # cheap + fast, plenty for a one-line read

# --- Data ---
LOOKBACK_PERIOD = "6mo"    # how much history to pull per ticker
INTERVAL = "1d"            # daily candles — this is a swing system, not intraday
