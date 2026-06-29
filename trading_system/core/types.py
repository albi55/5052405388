"""Shared data types — the contracts every other module speaks in.

These dataclasses are deliberately plain (no pandas in the public surface) so the
boundary between modules stays clear and testable. The two most important types
are Verdict (the ONLY thing the honesty layer hands back) and ValidationRecord
(the ONLY thing that can ever make a strategy eligible for execution).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


# ---------------------------------------------------------------------------
# Trades and simulation output
# ---------------------------------------------------------------------------
@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    direction: int           # +1 long, -1 short
    ret: float               # net fractional return after costs
    bars_held: int
    reason: str              # why it exited: target / stop / trail / time / signal

    @property
    def is_win(self) -> bool:
        return self.ret > 0


# ---------------------------------------------------------------------------
# The honesty layer's output
# ---------------------------------------------------------------------------
class OverfitRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class RiskMetrics:
    total_return: float
    max_drawdown: float
    return_dd_ratio: float
    worst_losing_streak: int
    longest_underwater_bars: int
    win_rate: float
    avg_trade: float
    n_trades: int


@dataclass
class Verdict:
    """The single public result of running the honesty layer. There is no API
    that returns a bare equity curve — a result is always a Verdict, which means
    it always carries the out-of-sample number, the costs used, and the flags."""
    symbol: str
    timeframe: str
    in_sample: RiskMetrics
    out_of_sample: RiskMetrics
    overfit_risk: OverfitRisk
    flags: list[str] = field(default_factory=list)         # human-readable warnings
    survives: bool = False                                 # the bottom-line verdict
    regime_note: str = ""                                  # random-walk / trend diagnostic summary
    params_frozen: dict[str, Any] = field(default_factory=dict)
    cost_summary: dict[str, float] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["overfit_risk"] = self.overfit_risk.value
        return d


# ---------------------------------------------------------------------------
# The gate artifact — the ONLY key that unlocks execution eligibility
# ---------------------------------------------------------------------------
@dataclass
class ValidationRecord:
    """A strategy becomes eligible for execution ONLY by possessing one of these,
    and one can ONLY be created by a human running gate/promote.py after BOTH an
    out-of-sample survival AND a multi-week demo run. Research never writes this.

    In this build, none exist, so the execution runner has nothing to run."""
    strategy_id: str
    spec_json: str
    oos_survived: bool
    oos_verdict_id: int | None
    demo_run_started: str | None       # ISO timestamp; None until a demo run is logged
    demo_run_days: int                 # must clear the configured minimum
    promoted_by: str                   # human who ran the gate
    promoted_at: str
    notes: str = ""

    def is_eligible(self, min_demo_days: int) -> bool:
        return (
            self.oos_survived
            and self.demo_run_started is not None
            and self.demo_run_days >= min_demo_days
        )
