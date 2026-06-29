"""Autonomous research loop — time-budgeted search with HONEST anti-overfitting.

The danger this is built to avoid: testing many strategies and reporting the best
is itself overfitting. The best of N tries looks good by luck. So the loop uses a
THREE-WAY split and a multiple-testing correction:

  For each generated strategy:
    1. optimize its inner param sweep on TRAIN,
    2. rank it by its VALIDATION return (out-of-sample to the strategy, but the
       loop sees many, so validation gets selection-contaminated over the run).
  After the whole search:
    3. take the SINGLE best strategy by validation,
    4. commit it and check it ONCE on the locked HOLDOUT (never optimized against),
    5. deflate that holdout return by a haircut scaled to how many strategies were
       tried (expected-max-of-N-noise), and
    6. declare an edge ONLY if the deflated holdout return is still positive on a
       usable sample with contained risk.

The loop NEVER auto-promotes to execution. A survivor is flagged for the manual
demo + gate, exactly like a single research run.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from ..core.strategy_spec import StrategySpec, set_by_path
from ..config.costs import resolve_cost
from ..backtest.engine import run_backtest
from ..honesty import metrics as M
from ..honesty.holdout import ThreeWaySplit
from ..data.rate_proxy import get_rate_differential, PROXY_WARNING


@dataclass
class Candidate:
    spec_name: str
    symbol: str
    timeframe: str
    family: str
    best_params: dict
    train_return: float
    validation_return: float
    validation_trades: int
    validation_dd: float
    proxy: bool = False


@dataclass
class LoopResult:
    tested: int = 0
    candidates: list = field(default_factory=list)   # all, ranked by validation
    finalist: Candidate | None = None
    holdout_return: float | None = None
    holdout_trades: int | None = None
    holdout_dd: float | None = None
    deflated_holdout: float | None = None
    edge_found: bool = False
    notes: list = field(default_factory=list)


def _apply(spec: StrategySpec, params: dict) -> StrategySpec:
    d = spec.to_dict()
    for path, v in params.items():
        set_by_path(d, path, v)
    return StrategySpec.from_dict(d)


def _sweep_combos(spec: StrategySpec) -> list[dict]:
    if not spec.sweep:
        return [{}]
    combos = [{}]
    for path, values in spec.sweep.items():
        combos = [dict(c, **{path: v}) for c in combos for v in values]
    return combos


def _external_for(spec: StrategySpec, bars):
    """Carry strategies need an external series. Returns (series, is_proxy)."""
    if spec.entry.type == "rate_differential":
        return get_rate_differential(bars), True
    return None, False


def _best_on(bars, spec, combos, cost, external):
    """Optimize the inner sweep on `bars`; return (best_params, best_metrics)."""
    best = None
    for params in combos:
        s = _apply(spec, params)
        trades = run_backtest(s, bars, cost, external=external)
        m = M.compute_metrics(trades)
        if best is None or m.total_return > best[1].total_return:
            best = (params, m)
    return best


def multiple_testing_haircut(best_return: float, n_strategies: int,
                             n_trades: int) -> float:
    """Deflate the finalist's return for having been chosen as best-of-N.
    Expected max of N noise draws scales ~ sqrt(2 ln N); per-trade noise ~
    1/sqrt(trades). Conservative and clearly heuristic."""
    if n_strategies <= 1 or n_trades <= 0:
        return best_return
    inflation = math.sqrt(2.0 * math.log(n_strategies))
    noise_per = 1.0 / math.sqrt(n_trades)
    haircut = inflation * noise_per * abs(best_return)
    return best_return - math.copysign(haircut, best_return)


def run_loop(specs, bars_by_key, time_budget_s, min_trades=30, log=print) -> LoopResult:
    """bars_by_key: dict mapping (symbol, timeframe) -> list[Bar]. Specs whose
    (symbol, timeframe) is missing from bars_by_key are skipped (no data)."""
    result = LoopResult()
    start = time.monotonic()

    # Build one ThreeWaySplit per (symbol, timeframe) so TRAIN/VALIDATION/HOLDOUT
    # boundaries are consistent across all strategies on the same series.
    splits = {}
    for key, bars in bars_by_key.items():
        if len(bars) > 250:
            splits[key] = ThreeWaySplit(bars)

    any_proxy = False
    for spec in specs:
        if time.monotonic() - start > time_budget_s:
            result.notes.append(f"time budget reached after {result.tested} strategies")
            break
        key = (spec.symbol, spec.timeframe)
        if key not in splits:
            continue
        split = splits[key]
        cost = resolve_cost(spec.symbol, None)   # floored cost; loop is offline-safe
        combos = _sweep_combos(spec)

        ext_train, is_proxy = _external_for(spec, split.train)
        ext_val, _ = _external_for(spec, split.validation)
        any_proxy = any_proxy or is_proxy

        # optimize on TRAIN, evaluate the frozen winner on VALIDATION
        best_params, _train_m = _best_on(split.train, spec, combos, cost, ext_train)
        frozen = _apply(spec, best_params)
        val_trades = run_backtest(frozen, split.validation, cost, external=ext_val)
        val_m = M.compute_metrics(val_trades)
        # also record train return of the chosen params for context
        train_trades = run_backtest(frozen, split.train, cost, external=ext_train)
        train_m = M.compute_metrics(train_trades)

        cand = Candidate(
            spec_name=spec.name, symbol=spec.symbol, timeframe=spec.timeframe,
            family="carry" if is_proxy else "price",
            best_params=best_params,
            train_return=train_m.total_return,
            validation_return=val_m.total_return,
            validation_trades=val_m.n_trades,
            validation_dd=val_m.max_drawdown,
            proxy=is_proxy,
        )
        result.candidates.append(cand)
        result.tested += 1
        log(f"  [{result.tested:>3}] {spec.name:<22} "
            f"val={val_m.total_return*100:+6.2f}% trades={val_m.n_trades:>3} "
            f"{'(proxy)' if is_proxy else ''}")

    if any_proxy:
        result.notes.append(PROXY_WARNING)

    # Rank by validation return, require a usable validation sample.
    usable = [c for c in result.candidates if c.validation_trades >= min_trades]
    usable.sort(key=lambda c: c.validation_return, reverse=True)
    if not usable:
        result.notes.append("no strategy reached the minimum validation sample; "
                            "no finalist eligible for the holdout")
        return result

    finalist = usable[0]
    result.finalist = finalist

    # ---- THE ONE LOOK AT THE HOLDOUT ------------------------------------
    key = (finalist.symbol, finalist.timeframe)
    split = splits[key]
    split.commit_final(finalist.spec_name)        # single-use lock
    spec = next(s for s in specs if s.name == finalist.spec_name)
    frozen = _apply(spec, finalist.best_params)
    cost = resolve_cost(finalist.symbol, None)
    ext_hold, _ = _external_for(spec, split.holdout())
    hold_trades = run_backtest(frozen, split.holdout(), cost, external=ext_hold)
    hold_m = M.compute_metrics(hold_trades)

    result.holdout_return = hold_m.total_return
    result.holdout_trades = hold_m.n_trades
    result.holdout_dd = hold_m.max_drawdown

    # ---- multiple-testing correction ------------------------------------
    deflated = multiple_testing_haircut(
        hold_m.total_return, result.tested, hold_m.n_trades)
    result.deflated_holdout = deflated

    # ---- the bottom line -------------------------------------------------
    result.edge_found = bool(
        not finalist.proxy                           # proxy results never count as real edge
        and hold_m.n_trades >= min_trades
        and deflated > 0
        and (hold_m.max_drawdown == 0 or hold_m.total_return / abs(hold_m.max_drawdown) >= 0.5)
    )
    if finalist.proxy:
        result.notes.append("finalist is a CARRY PROXY strategy — cannot count as a "
                            "real edge until a real rate feed replaces the proxy")
    return result
