"""
Mean-reversion vs trend vs random-walk diagnostic for daily EUR/USD.

This tests a PROPERTY OF THE ASSET, not a strategy. No entry, no exit, no
parameters to overfit. The question: what is the autocorrelation structure of
daily EUR/USD returns?

  - Mean-reverting  -> down moves tend to be followed by up moves
                       (negative autocorrelation; variance ratio < 1)
  - Trending        -> moves tend to persist
                       (positive autocorrelation; variance ratio > 1)
  - Random walk     -> no linear predictability either way
                       (autocorrelation ~ 0; variance ratio ~ 1)

Three independent lenses, so we're not leaning on one fragile statistic:
  1. Lag-k autocorrelation of daily log returns (k = 1..5).
  2. Lo-MacKinlay variance-ratio test across horizons (the standard trend-vs-
     reversion diagnostic). VR(q) = Var(q-day return) / (q * Var(1-day return)).
  3. Direct conditional check: after an N-day cumulative DECLINE, what is the
     average NEXT-day return? (This is literally the dip-buyer's premise.)

All read-only. Uses backtest.fetch_bars() so the data/accounting source is
identical to every other test in this project.
"""

import math
import backtest as bt


def log_returns(bars):
    out = []
    for i in range(1, len(bars)):
        out.append(math.log(bars[i]["close"] / bars[i - 1]["close"]))
    return out


def mean(xs):
    return sum(xs) / len(xs)


def autocorr(rets, lag):
    """Sample autocorrelation of rets at the given lag."""
    n = len(rets)
    m = mean(rets)
    denom = sum((r - m) ** 2 for r in rets)
    if denom == 0:
        return 0.0
    num = sum((rets[i] - m) * (rets[i - lag] - m) for i in range(lag, n))
    return num / denom


def variance_ratio(rets, q):
    """Lo-MacKinlay variance ratio for horizon q.
    VR < 1 => mean reversion; VR > 1 => trending; VR ~ 1 => random walk.
    Returns (vr, z_stat) with the heteroskedasticity-consistent... no — we use
    the simpler homoskedastic z, which is plenty for a directional read."""
    n = len(rets)
    m = mean(rets)
    var1 = sum((r - m) ** 2 for r in rets) / (n - 1)
    if var1 == 0:
        return 1.0, 0.0
    # q-period overlapping returns
    qsums = [sum(rets[i:i + q]) for i in range(0, n - q + 1)]
    mq = q * m
    varq = sum((s - mq) ** 2 for s in qsums) / (len(qsums) * q)
    vr = varq / var1
    # Homoskedastic z-stat for H0: VR = 1
    phi = (2.0 * (2 * q - 1) * (q - 1)) / (3.0 * q * n)
    z = (vr - 1.0) / math.sqrt(phi) if phi > 0 else 0.0
    return vr, z


def conditional_after_decline(bars, rets, n_down):
    """After n_down consecutive-cumulative down days, what's the avg next-day
    return? Compares it to the unconditional average. This is the dip premise."""
    # rets[i] is the return from bar i to bar i+1 (index shift handled by caller).
    nxt_after, all_next = [], rets[:]
    for i in range(n_down, len(rets)):
        window = rets[i - n_down:i]
        if sum(window) < 0:                       # cumulative decline over window
            nxt_after.append(rets[i])
    return nxt_after, all_next


def main():
    bars, _ = bt.fetch_bars()
    rets = log_returns(bars)
    n = len(rets)
    print(f"Analyzing {n} daily log returns "
          f"({bars[0]['time'].date()} -> {bars[-1]['time'].date()})\n")

    # --- Lens 1: autocorrelation -------------------------------------------
    print("=" * 70)
    print("LENS 1 — Autocorrelation of daily returns")
    print("  negative => mean-reverting | positive => trending | ~0 => random")
    print("=" * 70)
    # ~2-sigma significance band for autocorrelation under white noise.
    band = 2.0 / math.sqrt(n)
    print(f"  (95% noise band: +/- {band:.4f})")
    for lag in range(1, 6):
        ac = autocorr(rets, lag)
        flag = "significant" if abs(ac) > band else "noise"
        print(f"  lag {lag}:  {ac:+.4f}   [{flag}]")

    # --- Lens 2: variance ratio --------------------------------------------
    print("\n" + "=" * 70)
    print("LENS 2 — Variance ratio (Lo-MacKinlay)")
    print("  VR<1 => mean-reverting | VR>1 => trending | VR~1 => random walk")
    print("  |z|>2 => statistically distinguishable from random walk")
    print("=" * 70)
    for q in (2, 5, 10, 20):
        vr, z = variance_ratio(rets, q)
        if abs(z) <= 2:
            verdict = "random walk (not distinguishable)"
        elif vr < 1:
            verdict = "MEAN-REVERTING"
        else:
            verdict = "TRENDING"
        print(f"  q={q:>2}:  VR={vr:.3f}   z={z:+.2f}   -> {verdict}")

    # --- Lens 3: the dip-buyer's premise, measured directly ----------------
    print("\n" + "=" * 70)
    print("LENS 3 — Average NEXT-day return after a cumulative decline")
    print("  (this is literally what the dip-buying entry bets on)")
    print("=" * 70)
    uncond = mean(rets)
    print(f"  Unconditional avg daily return: {uncond*100:+.4f}%")
    for n_down in (1, 2, 3, 5):
        after, _ = conditional_after_decline(bars, rets, n_down)
        if not after:
            continue
        avg = mean(after)
        edge = avg - uncond
        direction = "bounce (supports dip-buy)" if avg > 0 else "keeps falling (refutes dip-buy)"
        print(f"  after {n_down}-day decline (n={len(after):>4}):  "
              f"next-day avg {avg*100:+.4f}%   vs uncond {edge*100:+.4f}%   -> {direction}")

    print("\n" + "=" * 70)
    print("HOW TO READ THIS")
    print("=" * 70)
    print("  If lenses agree on MEAN-REVERTING: the dip idea is sound; we were")
    print("    measuring the dislocation wrong -> build the volatility/z-score entry.")
    print("  If they agree on TRENDING: we've been fighting the asset -> flip to")
    print("    momentum (buy strength, not weakness).")
    print("  If they agree on RANDOM WALK: no linear daily edge either direction;")
    print("    that cleanly explains every out-of-sample failure. Change timeframe")
    print("    or asset, or accept there's no daily edge here to find.")


if __name__ == "__main__":
    main()
