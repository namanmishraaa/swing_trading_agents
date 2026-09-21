"""
Entry point. Run this once a day after market close:
    python main.py
For a recurring schedule, call this from cron / Windows Task Scheduler —
this script intentionally does not loop or sleep on its own.
"""

from dotenv import load_dotenv

from config import (
    CAPITAL,
    LLM_MODEL,
    MAX_POSITIONS,
    MIN_CONFIDENCE,
    RISK_PER_TRADE_PCT,
    USE_LLM_REASONING,
    WATCHLIST,
)
from orchestrator import Orchestrator


def main() -> None:
    load_dotenv()  # picks up ANTHROPIC_API_KEY from .env, if present

    orchestrator = Orchestrator(
        watchlist=WATCHLIST,
        capital=CAPITAL,
        risk_per_trade_pct=RISK_PER_TRADE_PCT,
        max_positions=MAX_POSITIONS,
        min_confidence=MIN_CONFIDENCE,
        use_llm=USE_LLM_REASONING,
        llm_model=LLM_MODEL,
    )
    decisions = orchestrator.run_cycle()

    print("\n=== Trade Decisions ===")
    if not decisions:
        print("No qualifying setups today.")
    for d in decisions:
        print(
            f"{d.ticker}: {d.action} {d.position_size} @ {d.entry} "
            f"| SL {d.stop_loss} | Target {d.target} | risking Rs.{d.risk_amount}"
        )


if __name__ == "__main__":
    main()
