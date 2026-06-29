"""
ATR-trailing-exit version of the in-sample / out-of-sample split test.

ONE variable changed vs split_test.py: the EXIT.
  - Entry: IDENTICAL (close >= entry_discount below the 20-day SMA, next-open fill).
  - Old exit (split_test.py): sell when price returns to the SMA, hard -3% stop.
  - New exit (here):           2*ATR(14) TRAILING stop from the highest close
                               since entry. Winners are allowed to run; the stop
                               ratchets up but never down.

Everything else is held constant so the comparison is clean:
  next-open fills, per-side spread cost, conservative intrabar (stop checked
  before any favorable move), one position at a time, no compounding.

Honest caveats specific to this version:
  * A trailing stop means trades can run for weeks/months. Overnight financing
    (swap) is NOT modeled, so a positive result here is slightly optimistic.
  * ATR is frozen at entry (trail distance fixed per trade) — simpler and avoids
    the stop loosening as volatility expands mid-trade.
"""

import backtest as bt

SMA_PERIOD = 20
ATR_PERIOD = 14
ATR_MULT   = 2.0
SWEEP = [0.005, 0.010, 0.015, 0.020]


def wilder_atr(bars, period):
    """ATR via Wilder smoothing. atr[i] uses True Range up to and including i.
    Returns a list aligned to bars; entries before warm-up are None."""
    n = len(bars)
    tr = [None] * n
    for i in range(n):
        h, l = bars[i]["high"], bars[i]["low"]
        if i == 0:
            tr[i] = h - l
        else:
            pc = bars[i - 1]["close"]
            tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    atr = [None] * n
    if n <= period:
        return atr
    # Seed with simple average of first `period` TRs, then Wilder-smooth.
    seed = sum(tr[1:period + 1]) / period
    atr[period] = seed
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def simulate_atr(bars, entry_discount, sma_period, cost_per_side):
    """Same entry as bt.simulate, but exit = 2*ATR trailing stop."""
    n = len(bars)
    sma = bt.rolling_sma(bars, sma_period)
    atr = wilder_atr(bars, ATR_PERIOD)

    in_pos = False
    entry_price = entry_time = None
    trail_dist = 0.0           # fixed 2*ATR distance for this trade
    high_close = 0.0           # highest close seen since entry
    trades = []
    equity = bt.START_EQUITY
    equity_curve = [bt.START_EQUITY]

    for i in range(n - 1):
        if sma[i] is None:
            continue
        nxt = bars[i + 1]

        if not in_pos:
            below = sma[i] * (1.0 - entry_discount)
            if bars[i]["close"] <= below and atr[i] is not None:
                entry_price = nxt["open"] + cost_per_side
                trail_dist = ATR_MULT * atr[i]      # freeze ATR at entry
                high_close = nxt["open"]
                entry_time = nxt["time"]
                in_pos = True
        else:
            stop_level = high_close - trail_dist
            # Conservative: test the trailing stop on the next bar's low first.
            if nxt["low"] <= stop_level:
                exit_price = stop_level - cost_per_side
                ret = (exit_price - entry_price) / entry_price
                equity *= (1.0 + ret)
                trades.append({
                    "entry_time": entry_time, "exit_time": nxt["time"],
                    "entry": entry_price, "exit": exit_price, "ret": ret,
                    "reason": "trail" if ret > 0 else "trail-loss",
                })
                equity_curve.append(equity)
                in_pos = False
            else:
                # Survived: ratchet the high (and thus the stop) upward only.
                high_close = max(high_close, nxt["close"])

    n_trades = len(trades)
    if n_trades == 0:
        return {"n_trades": 0, "total_return": 0.0, "win_rate": 0.0,
                "max_dd": 0.0, "stops": 0, "targets": 0, "avg_ret": 0.0,
                "final_equity": bt.START_EQUITY, "trades": []}

    wins = sum(1 for t in trades if t["ret"] > 0)
    total_return = (equity / bt.START_EQUITY) - 1.0
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        max_dd = min(max_dd, (v - peak) / peak)

    return {
        "n_trades": n_trades, "total_return": total_return,
        "win_rate": wins / n_trades, "max_dd": max_dd,
        "stops": sum(1 for t in trades if t["ret"] <= 0),   # losing trails
        "targets": wins,                                    # winning trails
        "avg_ret": sum(t["ret"] for t in trades) / n_trades,
        "final_equity": equity, "trades": trades,
    }


def fmt(s):
    return (f"trades={s['n_trades']:>3}  ret={s['total_return']*100:>7.2f}%  "
            f"win={s['win_rate']*100:>5.1f}%  avg/tr={s['avg_ret']*100:>6.2f}%  "
            f"maxDD={s['max_dd']*100:>7.2f}%  win/loss={s['targets']}/{s['stops']}")


def main():
    bars, cost_per_side = bt.fetch_bars()
    n = len(bars)
    mid = n // 2
    in_bars = bars[:mid]
    warmup = max(SMA_PERIOD, ATR_PERIOD)
    out_bars = bars[mid - warmup:]

    print("=" * 78)
    print("ATR-TRAILING-EXIT SPLIT TEST  (entry unchanged; only the exit differs)")
    print("=" * 78)
    print(f"In-sample : {in_bars[0]['time'].date()} -> {in_bars[-1]['time'].date()}  "
          f"({len(in_bars)} bars)")
    print(f"Out-sample: {out_bars[warmup]['time'].date()} -> {out_bars[-1]['time'].date()}  "
          f"({len(out_bars) - warmup} traded bars, +{warmup} warm-up)")
    print(f"Exit: {ATR_MULT}xATR({ATR_PERIOD}) trailing stop from highest close since entry\n")

    print("=" * 78)
    print(f"IN-SAMPLE OPTIMIZATION (sweep entry discount, {SMA_PERIOD}-day SMA)")
    print("=" * 78)
    best = None
    for disc in SWEEP:
        s = simulate_atr(in_bars, disc, SMA_PERIOD, cost_per_side)
        print(f"  entry {disc*100:>4.1f}% below SMA :  {fmt(s)}")
        if s["n_trades"] >= 10:
            if best is None or s["total_return"] > best[1]["total_return"]:
                best = (disc, s)

    if best is None:
        print("\nNo in-sample variation reached >=10 trades. Too thin. Stop.")
        return

    best_disc, best_in = best
    print(f"\n>> IN-SAMPLE WINNER: entry {best_disc*100:.1f}% below {SMA_PERIOD}-day SMA")
    print(f"   {fmt(best_in)}")
    print("   FROZEN. Nothing below is tuned.\n")

    print("=" * 78)
    print("OUT-OF-SAMPLE (blind)")
    print("=" * 78)
    out = simulate_atr(out_bars, best_disc, SMA_PERIOD, cost_per_side)
    print(f"  entry {best_disc*100:.1f}% below {SMA_PERIOD}-day SMA :  {fmt(out)}\n")

    print("=" * 78)
    print("SIDE BY SIDE")
    print("=" * 78)
    print(f"  IN-SAMPLE  (tuned) : {fmt(best_in)}")
    print(f"  OUT-SAMPLE (blind) : {fmt(out)}")

    print("\nOut-of-sample trade log:")
    if out["trades"]:
        print(f"  {'entry':>10}  {'exit':>10}  {'in':>8} {'out':>8}  {'ret%':>7}  reason")
        for t in out["trades"]:
            print(f"  {t['entry_time'].date()!s:>10}  {t['exit_time'].date()!s:>10}  "
                  f"{t['entry']:>8.5f} {t['exit']:>8.5f}  {t['ret']*100:>7.2f}  {t['reason']}")
    else:
        print("  (no trades fired out-of-sample)")


if __name__ == "__main__":
    main()
