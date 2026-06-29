"""Autonomous research loop CLI — runs all day, hunts for an edge HONESTLY.

It generates many strategies, tests each on a three-way split, ranks on
validation, then checks ONLY the single best finalist once on a locked holdout,
with a multiple-testing haircut. It reports a summary — never a hand-picked,
un-corrected 'winner'. It NEVER promotes anything to execution; survivors are
flagged for your manual demo + gate.

Usage:
  # run for 1 hour over price + carry families on the default universe
  python -m trading_system.apps.loop_cli --minutes 60

  # run all day (8 hours), price-only
  python -m trading_system.apps.loop_cli --minutes 480 --families price

  # quick smoke test
  python -m trading_system.apps.loop_cli --minutes 1 --pairs EURUSD --timeframes D1
"""

from __future__ import annotations

import argparse

from ..data.source_mt5 import MT5Source
from ..data.cache import load_bars
from ..search.generator import generate, DEFAULT_PAIRS, DEFAULT_TIMEFRAMES
from ..search.loop import run_loop
from ..records.store import SQLiteRecordStore


def _needed_keys(specs):
    return sorted({(s.symbol, s.timeframe) for s in specs})


def main():
    ap = argparse.ArgumentParser(description="Autonomous, honest strategy search.")
    ap.add_argument("--minutes", type=float, default=60, help="time budget in minutes")
    ap.add_argument("--families", nargs="+", default=["price", "carry"],
                    choices=["price", "carry"])
    ap.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS)
    ap.add_argument("--timeframes", nargs="+", default=DEFAULT_TIMEFRAMES)
    ap.add_argument("--bars", type=int, default=3000)
    ap.add_argument("--force-refresh", action="store_true")
    args = ap.parse_args()

    specs = generate(families=tuple(args.families), pairs=args.pairs,
                     timeframes=args.timeframes)
    keys = _needed_keys(specs)
    print(f"Generated {len(specs)} strategies across {len(keys)} data series.")
    print(f"Time budget: {args.minutes:.0f} min. Families: {args.families}\n")

    # Pull all required data once, up front.
    bars_by_key = {}
    with MT5Source() as src:
        for sym, tf in keys:
            try:
                bars, _ = load_bars(src, sym, tf, args.bars,
                                    force_refresh=args.force_refresh)
                bars_by_key[(sym, tf)] = bars
                print(f"  data: {sym} {tf}: {len(bars)} bars")
            except Exception as e:
                print(f"  data: {sym} {tf}: SKIPPED ({e})")
    print()

    print("Searching (validation returns shown; NOT the verdict):")
    result = run_loop(specs, bars_by_key, time_budget_s=args.minutes * 60.0)

    print("\n" + "=" * 78)
    print("LOOP SUMMARY")
    print("=" * 78)
    print(f"  Strategies tested: {result.tested}")
    if result.finalist is None:
        print("  No finalist reached the minimum validation sample.")
    else:
        f = result.finalist
        print(f"  Best by validation: {f.spec_name} "
              f"(val {f.validation_return*100:+.2f}%, {f.validation_trades} trades)")
        print(f"  Frozen params: {f.best_params}")
        print()
        print("  --- THE ONE LOOK AT THE LOCKED HOLDOUT (the real verdict) ---")
        print(f"  Holdout return:        {result.holdout_return*100:+.2f}% "
              f"on {result.holdout_trades} trades, DD {result.holdout_dd*100:+.2f}%")
        print(f"  After multiple-testing haircut ({result.tested} tries): "
              f"{result.deflated_holdout*100:+.2f}%")
        print()
        print(f"  >>> EDGE FOUND: {'YES' if result.edge_found else 'NO'} <<<")
    if result.notes:
        print("\n  Notes:")
        for n in result.notes:
            print(f"    - {n}")

    print("\n" + "=" * 78)
    if result.edge_found:
        print("A candidate survived the holdout + correction. This is NOT a green")
        print("light to trade. Next step is a multi-week DEMO run, then the manual")
        print("gate. The loop never promotes anything itself.")
    else:
        print("Nothing survived honestly. That is a real result, not a failure —")
        print("the loop refused to hand you a lucky ghost. Back to the loop with a")
        print("different hypothesis (e.g. a REAL rate feed for carry).")
    print("=" * 78)


if __name__ == "__main__":
    main()
