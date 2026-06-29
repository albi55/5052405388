"""Overfit detection — the checks that caught every ghost we killed by hand:
parameter instability across slices, large in-sample/out-of-sample degradation,
and dependence on a single narrow parameter value.

Each check returns flags (human-readable strings). assess_overfit_risk combines
them into a LOW/MEDIUM/HIGH rating.
"""

from __future__ import annotations

from ..core.types import RiskMetrics, OverfitRisk
from ..config.settings import OVERFIT_IS_OOS_GAP, PARAM_INSTABILITY_TOLERANCE


def is_oos_gap_flags(in_s: RiskMetrics, out_s: RiskMetrics) -> list[str]:
    flags = []
    gap = in_s.total_return - out_s.total_return
    if out_s.total_return <= 0 < in_s.total_return:
        flags.append(
            f"OVERFIT: positive in-sample ({in_s.total_return*100:+.2f}%) collapses "
            f"to non-positive out-of-sample ({out_s.total_return*100:+.2f}%)")
    elif gap > OVERFIT_IS_OOS_GAP:
        flags.append(
            f"DEGRADATION: in-sample beats out-of-sample by {gap*100:.2f}% "
            f"(threshold {OVERFIT_IS_OOS_GAP*100:.0f}%) — likely fitting noise")
    if out_s.max_drawdown < in_s.max_drawdown * 1.5 and out_s.max_drawdown < -0.001:
        flags.append(
            f"RISK GREW OUT-OF-SAMPLE: drawdown {out_s.max_drawdown*100:.2f}% "
            f"vs in-sample {in_s.max_drawdown*100:.2f}%")
    return flags


def parameter_stability_flags(best_per_slice: list[dict]) -> list[str]:
    """best_per_slice: list of the winning param dicts from each data slice.
    If the optimal value of any swept parameter jumps around across slices, the
    'edge' has no stable location — the signature of curve-fitting. We saw the
    optimal discount move 1.5% -> 0.5% -> 1.0% across slices; this catches that."""
    flags = []
    if len(best_per_slice) < 2:
        return flags
    keys = set().union(*[set(d.keys()) for d in best_per_slice])
    for k in keys:
        values = [d[k] for d in best_per_slice if k in d and isinstance(d[k], (int, float))]
        if len(values) < 2:
            continue
        lo, hi = min(values), max(values)
        if lo == hi:
            continue
        spread = (hi - lo) / (abs(hi) + abs(lo) + 1e-12)
        if spread > PARAM_INSTABILITY_TOLERANCE:
            flags.append(
                f"UNSTABLE PARAMETER '{k}': best value ranges {lo} .. {hi} across "
                f"slices — no stable optimum, likely curve-fit")
    return flags


def single_param_dependence_flags(sweep_results: list[tuple[dict, RiskMetrics]]) -> list[str]:
    """If only ONE parameter combo is profitable and its neighbors are not, the
    result sits on a knife-edge — fragile and probably fit. We check whether the
    best result is an isolated spike vs part of a profitable plateau."""
    flags = []
    profitable = [(p, m) for p, m in sweep_results if m.total_return > 0]
    if not sweep_results:
        return flags
    if len(profitable) == 1 and len(sweep_results) >= 4:
        flags.append(
            "KNIFE-EDGE: exactly one parameter combo is profitable out of "
            f"{len(sweep_results)} tested — fragile, no profitable plateau")
    return flags


def assess_overfit_risk(flags: list[str]) -> OverfitRisk:
    text = " ".join(flags).upper()
    hard = ("OVERFIT" in text) or ("KNIFE-EDGE" in text) or ("UNSTABLE PARAMETER" in text)
    soft = ("DEGRADATION" in text) or ("RISK GREW" in text)
    if hard:
        return OverfitRisk.HIGH
    if soft:
        return OverfitRisk.MEDIUM
    return OverfitRisk.LOW
