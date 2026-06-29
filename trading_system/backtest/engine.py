"""The simulation engine: StrategySpec + bars -> list[Trade].

Core honesty guarantees baked in here, not optional:
  * NEXT-OPEN FILLS. A signal is detected on bar i's close; the position is
    opened/closed at bar i+1's open. You cannot trade at a close you have not
    seen. This is the #1 defense against look-ahead bias.
  * COSTS PER SIDE. Every entry and exit pays cost_model.per_side() in price
    units, sourced through config.costs.resolve_cost() which floors the spread.
    A zero-cost run is not reachable from here.
  * SWAP. Positions held overnight accrue cost_model.swap_per_day per bar held.
  * CONSERVATIVE INTRABAR. Exit geometry (rules.evaluate_exit) tests the stop
    before the target within a bar, so results are never flattered.

The loop is explicit (not fully vectorized) because path-dependent exits
(trailing stops, one-position-at-a-time) are inherently sequential. Indicators
ARE vectorized (the expensive part); the loop is O(n) and fast enough for sweeps.
"""

from __future__ import annotations

import numpy as np

from ..core.types import Bar, Trade
from ..core.strategy_spec import StrategySpec
from ..config.costs import CostModel
from ..strategy import indicators as ind
from ..strategy.signals import entry_signal
from ..strategy.rules import OpenPosition, evaluate_exit
from ..strategy.sizing import notional_for


def _to_arrays(bars: list[Bar]) -> dict:
    return {
        "open": np.array([b.open for b in bars], dtype=float),
        "high": np.array([b.high for b in bars], dtype=float),
        "low": np.array([b.low for b in bars], dtype=float),
        "close": np.array([b.close for b in bars], dtype=float),
    }


def run_backtest(spec: StrategySpec, bars: list[Bar], cost: CostModel,
                 external: np.ndarray | None = None) -> list[Trade]:
    n = len(bars)
    if n < 3:
        return []
    arr = _to_arrays(bars)
    close, high, low, opn = arr["close"], arr["high"], arr["low"], arr["open"]

    enter = entry_signal(spec.entry, arr, spec.direction, external)

    # Precompute auxiliaries some exits need.
    sma_period = int(spec.exit.params.get("period", spec.entry.params.get("period", 20)))
    sma_series = ind.sma(close, sma_period) if spec.exit.type == "target_sma" else None
    atr_period = int(spec.exit.params.get("atr_period", 14))
    atr_mult = float(spec.exit.params.get("atr_mult", 2.0))
    atr_series = ind.atr(high, low, close, atr_period) if spec.exit.type == "atr_trailing" else None

    per_side = cost.per_side()
    swap = cost.swap_per_day
    d = spec.direction

    trades: list[Trade] = []
    pos: OpenPosition | None = None

    for i in range(n - 1):                 # need i+1 to fill on next open
        nxt = i + 1
        o, h, l, c = opn[nxt], high[nxt], low[nxt], close[nxt]

        if pos is None:
            if enter[i]:
                # Open at next open; pay cost adverse to our direction.
                fill = o + per_side * d
                pos = OpenPosition(
                    direction=d, entry_price=fill, entry_index=nxt,
                    sma_target=(sma_series[i] if sma_series is not None else None),
                )
                if spec.exit.type == "atr_trailing" and atr_series is not None and np.isfinite(atr_series[i]):
                    pos.trail_dist = atr_mult * atr_series[i]
                    pos.best_close = o
            continue

        # In a position: maybe update trailing state, then test exit.
        if spec.exit.type == "atr_trailing" and pos.best_close is not None:
            if d > 0:
                pos.best_close = max(pos.best_close, c)
            else:
                pos.best_close = min(pos.best_close, c)

        sma_now = sma_series[i] if sma_series is not None else None
        exit_price, reason = evaluate_exit(spec.exit, pos, h, l, c, nxt, sma_now)

        if exit_price is not None:
            # Pay cost adverse to closing (selling a long fills lower).
            fill = exit_price - per_side * d
            bars_held = nxt - pos.entry_index
            gross = (fill - pos.entry_price) / pos.entry_price * d
            swap_cost = swap * bars_held / pos.entry_price   # approx, in fractional terms
            ret = gross - swap_cost
            # Coerce numpy scalars to native Python types at the engine boundary,
            # so downstream metrics/verdicts are plain-Python and JSON-serializable.
            trades.append(Trade(
                entry_time=bars[pos.entry_index].time,
                exit_time=bars[nxt].time,
                entry_price=float(pos.entry_price),
                exit_price=float(fill),
                direction=int(d),
                ret=float(ret),
                bars_held=int(bars_held),
                reason=reason,
            ))
            pos = None

    return trades
