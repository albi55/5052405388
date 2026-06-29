"""
In-sample / out-of-sample split test for the EUR/USD mean-reversion rule.

The question this answers: did we FIND an edge, or did we FIT the noise?

Procedure (the honest one):
  1. Split the 10-year daily history in half by time.
  2. IN-SAMPLE (older half): sweep the entry discount, pick the best by total
     return. This is allowed to "cheat" — it sees the answer.
  3. OUT-OF-SAMPLE (newer half): run ONLY that frozen choice, once, blind.
     Nothing is tuned here. This is the number that matters.

If the in-sample winner also performs out-of-sample, the edge is plausibly real.
If it collapses out-of-sample, the in-sample result was curve-fit to noise.

Reuses simulate()/rolling_sma()/fetch_bars() from backtest.py unchanged, so the
accounting (next-open fills, per-side spread, conservative intrabar) is identical.
"""

import backtest as bt

SMA_PERIOD = 20                       # fixed: 10-day was confirmed worse
SWEEP = [0.005, 0.010, 0.015, 0.020]  # entry discounts to optimize over in-sample


def fmt(s):
    return (f"trades={s['n_trades']:>3}  ret={s['total_return']*100:>7.2f}%  "
            f"win={s['win_rate']*100:>5.1f}%  avg/tr={s['avg_ret']*100:>6.2f}%  "
            f"maxDD={s['max_dd']*100:>7.2f}%  tgt/stp={s['targets']}/{s['stops']}")


def main():
    bars, cost_per_side = bt.fetch_bars()
    n = len(bars)
    mid = n // 2

    in_bars = bars[:mid]
    # Out-of-sample: carry SMA_PERIOD warm-up bars so the first OOS signal uses a
    # fully-formed average. Those warm-up bars feed the SMA only; trading starts
    # after them, so no look-ahead and no cold-start distortion.
    warmup = SMA_PERIOD
    out_bars = bars[mid - warmup:]

    print("=" * 78)
    print("DATA SPLIT")
    print("=" * 78)
    print(f"In-sample : {in_bars[0]['time'].date()} -> {in_bars[-1]['time'].date()}  "
          f"({len(in_bars)} bars)")
    print(f"Out-sample: {out_bars[warmup]['time'].date()} -> {out_bars[-1]['time'].date()}  "
          f"({len(out_bars) - warmup} traded bars, +{warmup} warm-up)\n")

    # --- STEP 1: optimize on the in-sample half ----------------------------
    print("=" * 78)
    print(f"IN-SAMPLE OPTIMIZATION (sweep entry discount, {SMA_PERIOD}-day SMA)")
    print("=" * 78)
    best = None
    for disc in SWEEP:
        s = bt.simulate(in_bars, disc, SMA_PERIOD, cost_per_side)
        tag = f"  entry {disc*100:>4.1f}% below SMA :  {fmt(s)}"
        print(tag)
        # Pick winner by total return, but require a usable sample (>=10 trades)
        # so we don't crown a lucky 1-2 trade fluke.
        if s["n_trades"] >= 10:
            if best is None or s["total_return"] > best[1]["total_return"]:
                best = (disc, s)

    if best is None:
        print("\nNo in-sample variation reached >=10 trades. Sample too thin to "
              "optimize honestly. Stop here.")
        return

    best_disc, best_in = best
    print(f"\n>> IN-SAMPLE WINNER: entry {best_disc*100:.1f}% below {SMA_PERIOD}-day SMA")
    print(f"   {fmt(best_in)}")
    print("   This choice is now FROZEN. Nothing below is tuned.\n")

    # --- STEP 2: apply the frozen choice blind to out-of-sample ------------
    print("=" * 78)
    print("OUT-OF-SAMPLE (blind — frozen choice, never tuned on this data)")
    print("=" * 78)
    out = bt.simulate(out_bars, best_disc, SMA_PERIOD, cost_per_side)
    print(f"  entry {best_disc*100:.1f}% below {SMA_PERIOD}-day SMA :  {fmt(out)}\n")

    # --- The verdict, stated honestly --------------------------------------
    print("=" * 78)
    print("SIDE BY SIDE")
    print("=" * 78)
    print(f"  IN-SAMPLE  (tuned) : {fmt(best_in)}")
    print(f"  OUT-SAMPLE (blind) : {fmt(out)}")

    print("\nOut-of-sample trade log (the trades that count):")
    if out["trades"]:
        print(f"  {'entry':>10}  {'exit':>10}  {'in':>8} {'out':>8}  {'ret%':>7}  reason")
        for t in out["trades"]:
            print(f"  {t['entry_time'].date()!s:>10}  {t['exit_time'].date()!s:>10}  "
                  f"{t['entry']:>8.5f} {t['exit']:>8.5f}  {t['ret']*100:>7.2f}  {t['reason']}")
    else:
        print("  (no trades fired out-of-sample)")


if __name__ == "__main__":
    main()
