"""Component 1 entry point — the research tool you use daily.

Read-only. Pulls data via MT5, runs a strategy through the honest evaluation
pipeline, prints the verdict (OOS number as the headline), and persists the run.

Usage examples:
  python -m trading_system.apps.research_cli --example
  python -m trading_system.apps.research_cli --spec my_strategy.json
  python -m trading_system.apps.research_cli --history
  python -m trading_system.apps.research_cli --history --symbol EURUSD
"""

from __future__ import annotations

import argparse
import json

from ..core.strategy_spec import StrategySpec, SignalSpec, ExitSpec, SizingSpec
from ..data.source_mt5 import MT5Source
from ..data.cache import load_bars
from ..honesty.verdict import run_honest_evaluation
from ..records.store import SQLiteRecordStore
from ..records.query import summarize_history


def _example_spec() -> StrategySpec:
    """The dip-buy family we tested by hand, with a parameter sweep — so the
    honesty layer's overfit detection has something to chew on."""
    return StrategySpec(
        name="sma_dip_buy",
        symbol="EURUSD",
        timeframe="D1",
        direction=1,
        entry=SignalSpec(type="sma_discount", params={"period": 20, "discount": 0.01}),
        exit=ExitSpec(type="target_sma", params={"period": 20, "stop": 0.03}),
        sizing=SizingSpec(),
        sweep={"entry.params.discount": [0.005, 0.01, 0.015, 0.02]},
    )


def _print_metrics(label, m):
    print(f"  {label:<12} trades={m.n_trades:>3}  ret={m.total_return*100:>7.2f}%  "
          f"win={m.win_rate*100:>5.1f}%  avg/tr={m.avg_trade*100:>6.2f}%  "
          f"maxDD={m.max_drawdown*100:>7.2f}%  R/DD={m.return_dd_ratio:>5.2f}  "
          f"worstStreak={m.worst_losing_streak}")


def _print_verdict(v):
    print("=" * 78)
    print(f"VERDICT — {v.symbol} {v.timeframe}   (frozen params: {v.params_frozen})")
    print("=" * 78)
    print(f"  {v.regime_note}")
    print(f"  cost/side modeled: {v.cost_summary['per_side']:.5f} price "
          f"(spread {v.cost_summary['spread']:.5f}, never zero)\n")
    _print_metrics("IN-SAMPLE", v.in_sample)
    print("  (in-sample is TUNED — not evidence)\n")
    _print_metrics("OUT-SAMPLE", v.out_of_sample)
    print("  ^ this is the number that counts\n")
    print(f"  Overfit risk: {v.overfit_risk.value}")
    if v.flags:
        print("  Flags:")
        for f in v.flags:
            print(f"    - {f}")
    print()
    print(f"  >>> SURVIVES HONEST TESTING: {'YES' if v.survives else 'NO'} <<<")
    if not v.survives:
        print("      (not eligible for the validation gate; back to the loop)")
    print("=" * 78)


def cmd_run(spec: StrategySpec, bars_count: int, force_refresh: bool, frac: float):
    problems = spec.validate()
    if problems:
        raise SystemExit("invalid spec: " + "; ".join(problems))

    with MT5Source() as src:
        bars, _warnings = load_bars(src, spec.symbol, spec.timeframe, bars_count,
                                    force_refresh=force_refresh)
        live_spread = src.get_live_spread_price(spec.symbol)

    verdict = run_honest_evaluation(spec, bars, live_spread, in_sample_fraction=frac)
    _print_verdict(verdict)

    store = SQLiteRecordStore()
    vid = store.save_verdict(spec.to_json(), verdict)
    print(f"\nRecorded as verdict id {vid} "
          f"(searchable via --history; promote via gate/promote.py if it ever survives).")


def main():
    ap = argparse.ArgumentParser(description="Honest strategy research (read-only).")
    ap.add_argument("--spec", help="path to a strategy JSON spec")
    ap.add_argument("--example", action="store_true", help="run the built-in dip-buy example")
    ap.add_argument("--bars", type=int, default=2600, help="number of bars to pull")
    ap.add_argument("--in-sample-fraction", type=float, default=0.5)
    ap.add_argument("--force-refresh", action="store_true", help="bypass the data cache")
    ap.add_argument("--history", action="store_true", help="show past research runs and exit")
    ap.add_argument("--symbol", help="filter --history by symbol")
    args = ap.parse_args()

    if args.history:
        print(summarize_history(SQLiteRecordStore(), args.symbol))
        return

    if args.example:
        spec = _example_spec()
    elif args.spec:
        spec = StrategySpec.from_dict(json.loads(open(args.spec).read()))
    else:
        ap.error("provide --spec FILE or --example (or --history)")

    cmd_run(spec, args.bars, args.force_refresh, args.in_sample_fraction)


if __name__ == "__main__":
    main()
