"""
Every function here is a 'tool' — something an agent calls to get real work
done (fetch data, do math, ask an LLM). Agents never call these directly;
they go through the shared ToolRegistry, so any agent can reach any tool by
name and the actual logic is written exactly once. That's the "shared
tools" part of the brief.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import pandas as pd
import yfinance as yf


class ToolRegistry:
    """A shared toolbox. Build one in orchestrator.py and hand the same
    instance to all three agents."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        self._tools[name] = fn

    def call(self, name: str, *args, **kwargs):
        if name not in self._tools:
            raise KeyError(f"No tool registered as '{name}'")
        return self._tools[name](*args, **kwargs)


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def fetch_ohlcv(ticker: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Pull daily candles for one NSE ticker. Returns None instead of
    raising, so one bad ticker never kills a whole scan.

    Known gotcha: Yahoo Finance can lag on NSE (.NS) tickers, especially
    pre-market IST. If you get empty data, re-run after market close, or
    test against a past date range first to confirm the pipeline works.
    """
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        return df if not df.empty and len(df) >= 60 else None
    except Exception:
        return None


# --------------------------------------------------------------------------
# Indicators — hand-rolled in pandas so there's no TA-Lib install pain
# --------------------------------------------------------------------------

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window).mean()


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


# --------------------------------------------------------------------------
# Setup detection — this is "the strategy". Replace with your own logic.
# --------------------------------------------------------------------------

def detect_setup(df: pd.DataFrame) -> Optional[dict]:
    """Look at the most recent candle and decide if it's a swing-trade
    setup. Returns None if nothing qualifies.

    Deliberately simple: two textbook setups, long-only. Treat this as a
    starting point, not a proven strategy — backtest before trusting it
    with real money.
    """
    close = df["Close"]
    sma50 = compute_sma(close, 50)
    rsi = compute_rsi(close, 14)
    atr = compute_atr(df, 14)
    avg_volume = df["Volume"].rolling(20).mean()

    price = close.iloc[-1]
    uptrend = bool(price > sma50.iloc[-1])
    volume_spike = bool(df["Volume"].iloc[-1] > 1.5 * avg_volume.iloc[-1])
    recent_high = close.iloc[-20:-1].max()

    breakout = bool(price > recent_high) and volume_spike
    pullback = uptrend and 35 <= rsi.iloc[-1] <= 48

    if breakout:
        setup_type = "breakout"
    elif pullback:
        setup_type = "pullback"
    else:
        return None

    return {
        "setup_type": setup_type,
        "price": round(float(price), 2),
        "rsi": round(float(rsi.iloc[-1]), 1),
        "atr": round(float(atr.iloc[-1]), 2),
        "uptrend": uptrend,
        "volume_spike": volume_spike,
    }


# --------------------------------------------------------------------------
# Optional LLM reasoning — Predictor only calls this if USE_LLM_REASONING=True
# --------------------------------------------------------------------------

def llm_reasoning(alert, model: str) -> str:
    """Ask Claude for a one-line qualitative read on a setup. Falls back to
    a plain templated string if there's no API key, so the pipeline never
    breaks just because a key is missing."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return f"{alert.setup_type} setup, RSI {alert.rsi}, uptrend={alert.uptrend}"

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    prompt = (
        f"Ticker: {alert.ticker}\nSetup: {alert.setup_type}\nPrice: {alert.price}\n"
        f"RSI(14): {alert.rsi}\nATR(14): {alert.atr}\nAbove 50-day SMA: {alert.uptrend}\n\n"
        "In one short sentence, name the single biggest risk to watch for "
        "this setup. No recommendation, just the risk."
    )
    response = client.messages.create(
        model=model,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register("fetch_ohlcv", fetch_ohlcv)
    registry.register("detect_setup", detect_setup)
    registry.register("llm_reasoning", llm_reasoning)
