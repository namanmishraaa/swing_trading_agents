"""
Wires the three agents to one shared bus and one shared toolbox, then runs
a scan cycle. This is the only file that knows all three agents exist —
the agents themselves only know about the bus and the tools.
"""

from __future__ import annotations

from agents import CommanderAgent, MessageBus, PredictorAgent, TrackerAgent, TradeDecision
from tools import ToolRegistry, register_default_tools


class Orchestrator:
    def __init__(
        self,
        watchlist: list[str],
        capital: float,
        risk_per_trade_pct: float = 1.0,
        max_positions: int = 5,
        min_confidence: int = 65,
        use_llm: bool = False,
        llm_model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self.bus = MessageBus()
        self.tools = ToolRegistry()
        register_default_tools(self.tools)

        self.tracker = TrackerAgent(self.bus, self.tools, watchlist)
        self.predictor = PredictorAgent(self.bus, self.tools, use_llm, llm_model)
        self.commander = CommanderAgent(
            self.bus, self.tools, capital, risk_per_trade_pct, max_positions, min_confidence
        )

    def run_cycle(self) -> list[TradeDecision]:
        """One full pass: Tracker scans -> Predictor scores -> Commander
        decides. Everything downstream of scan() happens synchronously,
        because MessageBus calls handlers the moment something publishes."""
        self.tracker.scan()
        return self.commander.decisions
