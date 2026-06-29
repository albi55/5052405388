"""The honesty layer's single public entry point.

run_honest_evaluation() is the ONLY way to get a result, and it always returns a
Verdict. There is deliberately no public function that returns a bare equity
curve or an in-sample-only number, because that is how backtests lie. The
pipeline is fixed and non-optional:

  1. Diagnose the regime (random-walk warning) on the full history.
  2. Build a time-ordered DataSplit with OOS structurally locked.
  3. Optimize the parameter sweep on IN-SAMPLE only, across sub-slices, recording
     the winner per slice (for parameter-stability detection).
  4. FREEZE the chosen parameters.
  5. Only now read OUT-OF-SAMPLE and run the frozen strategy once, blind.
  6. Apply cost floor, compute risk metrics for both halves, run overfit and
     statistical checks, deflate for the number of trials.
  7. Assemble a Verdict with the OOS number as the headline and survives=...
"""

from __future__ import annotations

import copy

from ..core.types import Verdict, RiskMetrics
from ..core.strategy_spec import StrategySpec, set_by_path
from ..config.costs import CostModel, resolve_cost
from ..config.settings import MIN_TRADES_FOR_CONFIDENCE
from ..backtest.engine import run_backtest
from . import metrics as M
from . import overfit as OF
from . import statistics as ST
from . import regime as RG
from .split import DataSplit


def _apply_params(spec: StrategySpec, params: dict) -> StrategySpec:
    d = spec.to_dict()
    for path, value in params.items():
        set_by_path(d, path, value)
    return StrategySpec.from_dict(d)


def _enumerate_sweep(spec: StrategySpec) -> list[dict]:
    """Cartesian product of the sweep dict -> list of param dicts. No sweep => one
    empty dict (the spec as-is)."""
    if not spec.sweep:
        return [{}]
    paths = list(spec.sweep.keys())
    combos = [{}]
    for path in paths:
        new = []
        for c in combos:
            for v in spec.sweep[path]:
                cc = dict(c)
                cc[path] = v
                new.append(cc)
        combos = new
    return combos


def _best_on(bars, spec, combos, cost) -> tuple[dict, RiskMetrics, list]:
    """Return (best_params, best_metrics, all_results) by total return on `bars`,
    requiring a usable sample so a lucky 1-trade combo can't win."""
    results = []
    best = None
    for params in combos:
        s = _apply_params(spec, params)
        trades = run_backtest(s, bars, cost)
        m = M.compute_metrics(trades)
        results.append((params, m))
        if m.n_trades >= max(10, MIN_TRADES_FOR_CONFIDENCE // 3):
            if best is None or m.total_return > best[1].total_return:
                best = (params, m)
    if best is None:
        # Fall back to the highest-return combo regardless of sample, but it will
        # be flagged for tiny sample downstream.
        best = max(results, key=lambda r: r[1].total_return) if results else ({}, M.compute_metrics([]))
    return best[0], best[1], results


def run_honest_evaluation(spec: StrategySpec, bars: list,
                          live_spread_price: float | None,
                          in_sample_fraction: float = 0.5) -> Verdict:
    problems = spec.validate()
    if problems:
        raise ValueError("invalid strategy spec: " + "; ".join(problems))

    cost: CostModel = resolve_cost(spec.symbol, live_spread_price)
    combos = _enumerate_sweep(spec)

    # 1. regime
    regime_summary, _regime_detail = RG.diagnose(bars)

    # 2. split (OOS locked)
    split = DataSplit(bars, in_sample_fraction=in_sample_fraction)
    in_bars = split.in_sample

    # 3. optimize in-sample, and also per sub-slice for stability detection
    best_params, in_metrics, in_results = _best_on(in_bars, spec, combos, cost)

    # parameter stability across two halves of the in-sample window
    half = len(in_bars) // 2
    slice_winners = []
    for sl in (in_bars[:half], in_bars[half:]):
        if len(sl) > 60:
            bp, _, _ = _best_on(sl, spec, combos, cost)
            # only keep numeric swept values for stability comparison
            numeric = {k: v for k, v in bp.items() if isinstance(v, (int, float))}
            if numeric:
                slice_winners.append(numeric)

    # 4. FREEZE
    split.freeze(best_params)

    # 5. out-of-sample, blind, frozen params only
    out_bars = split.out_of_sample()
    frozen_spec = _apply_params(spec, best_params)
    out_trades = run_backtest(frozen_spec, out_bars, cost)
    out_metrics = M.compute_metrics(out_trades)

    # 6. checks
    flags: list[str] = []
    flags += OF.is_oos_gap_flags(in_metrics, out_metrics)
    flags += OF.parameter_stability_flags(slice_winners)
    flags += OF.single_param_dependence_flags(in_results)
    flags += ST.sample_size_flags(out_metrics.n_trades)
    _deflated, deflation_note = ST.deflate_for_trials(
        out_metrics.total_return, len(combos), out_metrics.n_trades)
    if len(combos) > 1:
        flags.append(deflation_note)

    overfit_risk = OF.assess_overfit_risk(flags)

    # 7. the bottom line: survives only if OOS is genuinely positive on a usable
    # sample, risk is contained, and overfit risk is not HIGH.
    survives = bool(
        out_metrics.n_trades >= MIN_TRADES_FOR_CONFIDENCE
        and out_metrics.total_return > 0
        and out_metrics.return_dd_ratio >= 0.5
        and overfit_risk != overfit_risk.HIGH
    )

    from datetime import datetime, timezone
    return Verdict(
        symbol=spec.symbol,
        timeframe=spec.timeframe,
        in_sample=in_metrics,
        out_of_sample=out_metrics,
        overfit_risk=overfit_risk,
        flags=flags,
        survives=survives,
        regime_note=regime_summary,
        params_frozen=best_params,
        cost_summary={
            "spread": cost.spread, "commission": cost.commission,
            "slippage": cost.slippage, "swap_per_day": cost.swap_per_day,
            "per_side": cost.per_side(),
        },
        created_at=datetime.now(timezone.utc).isoformat(),
    )
