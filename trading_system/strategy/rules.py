"""Exit rules. Given an open position and the next bar, decide whether/where it
exits. Returns (exit_price_before_cost, reason) or (None, None) to stay in.

Convention shared with the original research scripts and asserted in tests:
intrabar fills are CONSERVATIVE — within a single bar we assume the adverse
level (stop) is tested before the favorable one (target). This never flatters
results. Costs are applied by the engine, not here, so this stays pure geometry.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OpenPosition:
    direction: int
    entry_price: float
    entry_index: int
    # exit-state carried across bars:
    sma_target: float | None = None     # for target_sma
    stop_level: float | None = None     # for fixed_tp_sl / atr trailing
    tp_level: float | None = None       # for fixed_tp_sl
    trail_dist: float | None = None     # for atr_trailing (frozen at entry)
    best_close: float | None = None     # for atr_trailing ratchet


def evaluate_exit(exit_spec, pos: OpenPosition, nxt_high: float, nxt_low: float,
                  nxt_close: float, bar_index: int, sma_now: float | None):
    """Return (exit_price, reason) or (None, None). `sma_now` is the SMA value at
    the signal bar, used by target_sma."""
    t = exit_spec.type
    p = exit_spec.params
    d = pos.direction

    if t == "target_sma":
        target = sma_now if sma_now is not None else pos.sma_target
        if target is None:
            return None, None
        stop_frac = float(p.get("stop", 0.03))
        stop = pos.entry_price * (1.0 - stop_frac) if d > 0 else pos.entry_price * (1.0 + stop_frac)
        # conservative: test stop first
        if d > 0:
            if nxt_low <= stop:
                return stop, "stop"
            if nxt_high >= target:
                return target, "target"
        else:
            if nxt_high >= stop:
                return stop, "stop"
            if nxt_low <= target:
                return target, "target"
        return None, None

    if t == "fixed_tp_sl":
        tp_frac = float(p.get("take_profit", 0.02))
        sl_frac = float(p.get("stop_loss", 0.02))
        if d > 0:
            tp = pos.entry_price * (1.0 + tp_frac)
            sl = pos.entry_price * (1.0 - sl_frac)
            if nxt_low <= sl:
                return sl, "stop"
            if nxt_high >= tp:
                return tp, "target"
        else:
            tp = pos.entry_price * (1.0 - tp_frac)
            sl = pos.entry_price * (1.0 + sl_frac)
            if nxt_high >= sl:
                return sl, "stop"
            if nxt_low <= tp:
                return tp, "target"
        return None, None

    if t == "atr_trailing":
        # trail_dist and best_close are maintained by the engine each bar.
        if pos.trail_dist is None or pos.best_close is None:
            return None, None
        if d > 0:
            stop_level = pos.best_close - pos.trail_dist
            if nxt_low <= stop_level:
                return stop_level, "trail"
        else:
            stop_level = pos.best_close + pos.trail_dist
            if nxt_high >= stop_level:
                return stop_level, "trail"
        return None, None

    if t == "time":
        max_bars = int(p.get("bars", 10))
        if bar_index - pos.entry_index >= max_bars:
            return nxt_close, "time"
        return None, None

    raise ValueError(f"unknown exit type: {t}")
