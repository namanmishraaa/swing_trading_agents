"""
The three agents, plus the tiny message bus that lets them talk without
knowing about each other directly. Tracker publishes, Predictor and
Commander subscribe — nobody calls anybody else's methods directly.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable


# --------------------------------------------------------------------------
# Messages agents pass to each other
# --------------------------------------------------------------------------

@dataclass
class SetupAlert:
    ticker: str
    setup_type: str
    price: float
    rsi: float
    atr: float
    uptrend: bool
    volume_spike: bool


@dataclass
class Prediction:
    ticker: str
    setup_type: str
    price: float
    atr: float
    confidence: int   # 0-100 — a confluence score, not a probability
    reasoning: str


@dataclass
class TradeDecision:
    ticker: str
    action: str        # always "BUY" here — this system never auto-executes
    entry: float
    stop_loss: float
    target: float
    position_size: int
    risk_amount: float
    reasoning: str


# --------------------------------------------------------------------------
# Communication: a minimal pub/sub bus
# --------------------------------------------------------------------------

class MessageBus:
    """Agents publish to a topic; anyone subscribed to that topic gets
    called immediately, in order. No queues, no threads — deliberately
    simple so you can step through the whole flow in a debugger."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Callable) -> None:
        self._subscribers[topic].append(handler)

    def publish(self, topic: str, message) -> None:
        for handler in self._subscribers[topic]:
            handler(message)


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------

class BaseAgent:
    def __init__(self, name: str, bus: MessageBus, tools) -> None:
        self.name = name
        self.bus = bus
        self.tools = tools

    def log(self, msg: str) -> None:
        print(f"[{self.name}] {msg}")


class TrackerAgent(BaseAgent):
    """Watches the list. Fetches data, checks for a setup, shouts if it
    finds one. Doesn't judge quality — that's Predictor's job."""

    def __init__(self, bus: MessageBus, tools, watchlist: list[str]) -> None:
        super().__init__("Tracker", bus, tools)
        self.watchlist = watchlist

    def scan(self) -> None:
        self.log(f"scanning {len(self.watchlist)} tickers...")
        found = 0
        for ticker in self.watchlist:
            df = self.tools.call("fetch_ohlcv", ticker)
            if df is None:
                self.log(f"{ticker}: no usable data, skipping")
                continue
            setup = self.tools.call("detect_setup", df)
            if setup:
                found += 1
                self.log(f"{ticker}: {setup['setup_type']} setup")
                self.bus.publish("setup_alert", SetupAlert(ticker=ticker, **setup))
        self.log(f"scan complete — {found} setup(s) found")


class PredictorAgent(BaseAgent):
    """Scores each setup Tracker finds. 'Prediction' here means a
    confidence score built from indicator confluence, not a promise about
    where the price goes next — nobody can predict that."""

    def __init__(self, bus: MessageBus, tools, use_llm: bool, model: str) -> None:
        super().__init__("Predictor", bus, tools)
        self.use_llm = use_llm
        self.model = model
        bus.subscribe("setup_alert", self.handle_alert)

    def handle_alert(self, alert: SetupAlert) -> None:
        confidence = self._score(alert)
        if self.use_llm:
            reasoning = self.tools.call("llm_reasoning", alert, self.model)
        else:
            reasoning = f"{alert.setup_type}, RSI {alert.rsi}, uptrend={alert.uptrend}"

        self.log(f"{alert.ticker}: confidence {confidence}/100")
        self.bus.publish(
            "prediction",
            Prediction(
                ticker=alert.ticker,
                setup_type=alert.setup_type,
                price=alert.price,
                atr=alert.atr,
                confidence=confidence,
                reasoning=reasoning,
            ),
        )

    @staticmethod
    def _score(alert: SetupAlert) -> int:
        score = 50
        score += 20 if alert.setup_type == "breakout" else 0
        score += 15 if alert.volume_spike else 0
        score += 10 if alert.uptrend else 0
        score += 5 if 38 <= alert.rsi <= 45 else 0
        return min(score, 95)


class CommanderAgent(BaseAgent):
    """Turns a scored prediction into a sized trade decision, or skips it.
    Enforces the risk rules. Never places a real order — it only decides
    and logs. Wire in a broker API yourself when you're ready for that."""

    def __init__(
        self,
        bus: MessageBus,
        tools,
        capital: float,
        risk_per_trade_pct: float,
        max_positions: int,
        min_confidence: int,
    ) -> None:
        super().__init__("Commander", bus, tools)
        self.capital = capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_positions = max_positions
        self.min_confidence = min_confidence
        self.decisions: list[TradeDecision] = []
        bus.subscribe("prediction", self.handle_prediction)

    def handle_prediction(self, prediction: Prediction) -> None:
        if prediction.confidence < self.min_confidence:
            self.log(f"{prediction.ticker}: SKIP (confidence {prediction.confidence})")
            return
        if len(self.decisions) >= self.max_positions:
            self.log(f"{prediction.ticker}: SKIP (max positions reached)")
            return

        entry = prediction.price
        stop_loss = round(entry - 1.5 * prediction.atr, 2)
        target = round(entry + 2 * prediction.atr, 2)
        per_share_risk = entry - stop_loss
        risk_amount = self.capital * (self.risk_per_trade_pct / 100)
        position_size = int(risk_amount / per_share_risk) if per_share_risk > 0 else 0

        if position_size <= 0:
            self.log(f"{prediction.ticker}: SKIP (position size rounds to 0)")
            return

        decision = TradeDecision(
            ticker=prediction.ticker,
            action="BUY",
            entry=entry,
            stop_loss=stop_loss,
            target=target,
            position_size=position_size,
            risk_amount=round(risk_amount, 2),
            reasoning=prediction.reasoning,
        )
        self.decisions.append(decision)
        self.log(
            f"{prediction.ticker}: BUY {position_size} @ {entry} "
            f"| SL {stop_loss} | Target {target}"
        )
