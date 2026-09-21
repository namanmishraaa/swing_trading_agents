# Swing Trading Agent System (NSE)

Three small agents that work together to scan NSE stocks for swing-trade
setups, score them, and turn the good ones into sized trade decisions.
This is boilerplate — a clean starting point to build on, not a finished
strategy.

> **Not financial advice.** This is a coding tool, not a signal service.
> Backtest before trusting it with real money. If you later wire this
> into a broker API for live orders, check your broker's and SEBI's
> rules on algorithmic order placement first.

## How it works

```
Watchlist (NSE tickers, .NS suffix)
        │
        ▼
   ┌─────────┐  setup_alert   ┌───────────┐  prediction   ┌───────────┐
   │ Tracker │───────────────▶│ Predictor │──────────────▶│ Commander │
   └─────────┘                └───────────┘                └───────────┘
        └────────── shared ToolRegistry + MessageBus ──────────┘
```

- **Tracker** — pulls price/volume history for every ticker on the
  watchlist and checks it against two setups (breakout, pullback in an
  uptrend). Finds one → shouts it on the bus.
- **Predictor** — listens for those shouts and scores each one 0-100
  based on how many good signs line up (trend, volume, RSI). "Predictor"
  means a confidence score here, not a promise — nobody can predict a
  stock price. It can optionally also ask Claude for a one-line read on
  the key risk to watch.
- **Commander** — listens to Predictor, applies your risk rules (max
  risk per trade, max open positions), and works out entry, stop-loss,
  target, and position size using ATR. It only decides and prints — it
  never sends a real order.

They never call each other directly. Tracker publishes a message,
Predictor and Commander subscribe to the topics they care about — that's
the `MessageBus` in `agents.py`. All three also share one `ToolRegistry`
(in `tools.py`), so the actual work — fetching data, computing
indicators — is written once and reused by whoever needs it.

## Setup

```bash
pip install -r requirements.txt
# uv users: uv pip install -r requirements.txt

cp .env.example .env   # only needed if you turn on USE_LLM_REASONING
python main.py
```

Requires Python 3.10+.

## Files

| File | What's in it |
|---|---|
| `config.py` | Watchlist, capital, risk %, thresholds — the knobs |
| `tools.py` | Data fetch, indicator math, setup detection, optional LLM call |
| `agents.py` | The 3 agent classes, message types, the message bus |
| `orchestrator.py` | Wires everything together, runs one scan cycle |
| `main.py` | Entry point — run this |

## A known gotcha

Yahoo Finance (the free data source here, via `yfinance`) can lag on
`.NS` tickers, especially before NSE opens in IST. If a scan comes back
empty, re-run after market close, or test against a past date range
first to confirm the pipeline itself is working.

## Extending this

- **Live execution** — `CommanderAgent.handle_prediction` in `agents.py`
  is where you'd call a broker API (Zerodha Kite Connect, Upstox, etc.)
  instead of just logging. Start with paper trading.
- **More setups** — add logic to `detect_setup()` in `tools.py`. Nothing
  else needs to change; Predictor and Commander don't care how a setup
  was found.
- **Bigger watchlist** — edit `WATCHLIST` in `config.py`. Nifty 50/100
  tickers all use the `.NS` suffix.
- **Backtesting** — this boilerplate only looks at the latest candle each
  run. To backtest, loop `detect_setup()` over historical windows instead
  of just the last row.
