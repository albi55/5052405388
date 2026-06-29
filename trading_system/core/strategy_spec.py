"""StrategySpec — the configuration object that defines a strategy WITHOUT
rewriting core code. This is the shared language: research interprets it to
backtest; the gate freezes it; the (future) execution runner would consume the
exact same frozen spec. Expressing a strategy as data, not code, is also the
security posture — there is no user code to execute, only parameters to evaluate.

A spec is plain JSON-serializable data. Validation is explicit and stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
from typing import Any


# Vocabulary the engine knows how to evaluate. Adding a capability means adding
# to these lists and to the corresponding evaluator — never running user code.
SIGNAL_TYPES = {
    "sma_discount",      # close N% below an M-period SMA  (the dip-buy family)
    "zscore",            # close K std-devs below rolling mean (volatility-scaled)
    "rsi",               # RSI below/above a threshold
    "breakout",          # close beyond an N-bar high/low
    "rate_differential", # non-price: external carry signal (pluggable source)
}

EXIT_TYPES = {
    "target_sma",        # exit when price returns to the SMA
    "fixed_tp_sl",       # fixed take-profit / stop-loss percentages
    "atr_trailing",      # K*ATR trailing stop from best close since entry
    "time",              # exit after N bars
}

SIZING_TYPES = {"fixed_notional", "fixed_fractional", "volatility_scaled"}


@dataclass
class SignalSpec:
    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExitSpec:
    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SizingSpec:
    type: str = "fixed_notional"
    params: dict[str, Any] = field(default_factory=lambda: {"notional": 10_000.0})


@dataclass
class StrategySpec:
    name: str
    symbol: str
    timeframe: str
    direction: int                      # +1 long-only, -1 short-only
    entry: SignalSpec
    exit: ExitSpec
    sizing: SizingSpec = field(default_factory=SizingSpec)
    # Parameter sweep: maps a dotted path (e.g. "entry.params.discount") to a
    # list of values. The honesty layer uses this to optimize in-sample and to
    # measure parameter stability across slices.
    sweep: dict[str, list[Any]] = field(default_factory=dict)

    # -- serialization -----------------------------------------------------
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "StrategySpec":
        return StrategySpec(
            name=d["name"],
            symbol=d["symbol"],
            timeframe=d["timeframe"],
            direction=int(d["direction"]),
            entry=SignalSpec(**d["entry"]),
            exit=ExitSpec(**d["exit"]),
            sizing=SizingSpec(**d.get("sizing", {})),
            sweep=d.get("sweep", {}),
        )

    # -- validation --------------------------------------------------------
    def validate(self) -> list[str]:
        """Return a list of problems (empty == valid). Explicit, not exceptions,
        so callers can surface all issues at once."""
        problems = []
        if self.entry.type not in SIGNAL_TYPES:
            problems.append(f"unknown entry signal type: {self.entry.type!r}")
        if self.exit.type not in EXIT_TYPES:
            problems.append(f"unknown exit type: {self.exit.type!r}")
        if self.sizing.type not in SIZING_TYPES:
            problems.append(f"unknown sizing type: {self.sizing.type!r}")
        if self.direction not in (1, -1):
            problems.append("direction must be +1 (long) or -1 (short)")
        for path, values in self.sweep.items():
            if not isinstance(values, list) or not values:
                problems.append(f"sweep[{path!r}] must be a non-empty list")
        return problems


def set_by_path(spec_dict: dict, dotted: str, value: Any) -> None:
    """Set spec_dict['a']['b']['c'] = value for dotted='a.b.c'. Used to apply a
    swept parameter onto a spec without mutating the original."""
    keys = dotted.split(".")
    node = spec_dict
    for k in keys[:-1]:
        node = node[k]
    node[keys[-1]] = value
