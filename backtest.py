"""
Mean-reversion backtest on daily EUR/USD (read-only, historical analysis).

Rule under test:
  ENTRY (long): close is >= 2% below its 20-day SMA
  EXIT:
    - take profit: price returns to the 20-day SMA, OR
    - stop loss:   price falls a further 3% below the entry price

This script places NO real orders. It only pulls historical candles via
mt5.copy_rates_from_pos() and simulates the trades in memory.

Honest-accounting choices (these matter — read them):
  * Signals are computed on a day's CLOSE, but you cannot trade at a close you
    haven't seen yet. So entries/exits fill on the NEXT day's OPEN. This avoids
    look-ahead bias, which is the #1 way backtests lie.
  * Costs: we charge the live spread (from symbol_info) on entry AND exit, plus
    an optional slippage buffer. Spread on EURUSD is tiny but it's not zero, and
    a strategy that only works at zero cost doesn't work.
  * Intrabar fills for SL/TP are approximate: within a single daily candle we
    cannot know whether the high or low came first. We use a conservative
    convention (check stop before target) so results are not flattered.
  * One position at a time, fixed notional, no compounding, no leverage modeling.
    This isolates whether the RULE has edge, separate from money management.
"""

import sys
from datetime import datetime

import MetaTrader5 as mt5

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
SYMBOL          = "EURUSD"
TIMEFRAME       = mt5.TIMEFRAME_D1
LOOKBACK_DAYS   = 520          # ~2 years of trading days (markets ~252/yr)
SMA_PERIOD      = 20
ENTRY_DISCOUNT  = 0.02         # enter when 2% below SMA
STOP_FURTHER    = 0.03         # stop = 3% below entry price
SLIPPAGE_PRICE  = 0.00000      # extra adverse fill per side; set e.g. 0.00002 to stress-test
START_EQUITY    = 10_000.0     # notional traded per position (no compounding)


def get_spread_price(symbol):
    """Return the current spread expressed in PRICE units (not points)."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    # spread is in points; point is the price increment per point
    return info.spread * info.point


def main():
    if not mt5.initialize():
        print("Failed to connect to MT5:", mt5.last_error())
        sys.exit(1)

    try:
        info = mt5.symbol_info(SYMBOL)
        if info is None or not info.visible:
            # Symbol may exist but not be in Market Watch; try to select it.
            if not mt5.symbol_select(SYMBOL, True):
                print(f"Symbol {SYMBOL} not available:", mt5.last_error())
                sys.exit(1)
            info = mt5.symbol_info(SYMBOL)

        spread_price = get_spread_price(SYMBOL) or 0.0
        cost_per_side = spread_price + SLIPPAGE_PRICE

        rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, LOOKBACK_DAYS)
        if rates is None or len(rates) == 0:
            print("No rate data returned:", mt5.last_error())
            sys.exit(1)
    finally:
        # We have the data; no need to hold the terminal connection during sim.
        mt5.shutdown()

    # rates is a numpy structured array: time, open, high, low, close, tick_volume, ...
    bars = [
        {
            "time":  datetime.utcfromtimestamp(int(r["time"])),
            "open":  float(r["open"]),
            "high":  float(r["high"]),
            "low":   float(r["low"]),
            "close": float(r["close"]),
        }
        for r in rates
    ]

    n = len(bars)
    print(f"Pulled {n} daily {SYMBOL} candles: "
          f"{bars[0]['time'].date()} -> {bars[-1]['time'].date()}")
    print(f"Modeled cost per side: {cost_per_side:.5f} price "
          f"(spread {spread_price:.5f} + slippage {SLIPPAGE_PRICE:.5f})\n")

    # Rolling 20-day SMA of close, aligned so sma[i] uses closes [i-19 .. i].
    sma = [None] * n
    running = 0.0
    for i in range(n):
        running += bars[i]["close"]
        if i >= SMA_PERIOD:
            running -= bars[i - SMA_PERIOD]["close"]
        if i >= SMA_PERIOD - 1:
            sma[i] = running / SMA_PERIOD

    # -----------------------------------------------------------------------
    # Event loop. Signal on bar i's close -> act on bar i+1's open.
    # -----------------------------------------------------------------------
    in_pos = False
    entry_price = 0.0
    stop_price = 0.0
    trades = []          # list of dicts: entry/exit price, return, reason
    equity_curve = []    # equity after each closed trade, for drawdown

    equity = START_EQUITY

    for i in range(n - 1):          # i+1 must exist to fill on next open
        if sma[i] is None:
            continue

        nxt = bars[i + 1]

        if not in_pos:
            below = sma[i] * (1.0 - ENTRY_DISCOUNT)
            if bars[i]["close"] <= below:
                # Fill long at next open, pay half-cost (cost charged per side).
                entry_price = nxt["open"] + cost_per_side
                stop_price = nxt["open"] * (1.0 - STOP_FURTHER)
                in_pos = True
                entry_time = nxt["time"]
        else:
            target = sma[i]          # TP when price returns to the SMA
            exit_price = None
            reason = None

            # Conservative intrabar convention: assume the adverse (stop) level
            # is tested before the favorable (target) within the same candle.
            if nxt["low"] <= stop_price:
                exit_price = stop_price - cost_per_side
                reason = "stop"
            elif nxt["high"] >= target:
                exit_price = target - cost_per_side
                reason = "target"

            if exit_price is not None:
                ret = (exit_price - entry_price) / entry_price
                equity *= (1.0 + ret)
                trades.append({
                    "entry_time": entry_time,
                    "exit_time":  nxt["time"],
                    "entry":      entry_price,
                    "exit":       exit_price,
                    "ret":        ret,
                    "reason":     reason,
                })
                equity_curve.append(equity)
                in_pos = False

    # -----------------------------------------------------------------------
    # Honest results
    # -----------------------------------------------------------------------
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    if not trades:
        print("No trades triggered over the sample. The rule never fired —")
        print("a 2% daily discount to the 20-day SMA is rare on EUR/USD.")
        return

    n_trades = len(trades)
    wins = [t for t in trades if t["ret"] > 0]
    win_rate = len(wins) / n_trades
    total_return = (equity / START_EQUITY) - 1.0

    # Max drawdown on the equity curve (peak-to-trough), incl. starting point.
    curve = [START_EQUITY] + equity_curve
    peak = curve[0]
    max_dd = 0.0
    for v in curve:
        peak = max(peak, v)
        dd = (v - peak) / peak
        max_dd = min(max_dd, dd)

    stops = sum(1 for t in trades if t["reason"] == "stop")
    targets = sum(1 for t in trades if t["reason"] == "target")
    avg_ret = sum(t["ret"] for t in trades) / n_trades

    print(f"Total return (per-trade notional, no compounding edge): {total_return*100:7.2f}%")
    print(f"Final equity on {START_EQUITY:,.0f} notional:            {equity:,.2f}")
    print(f"Number of trades:                                       {n_trades}")
    print(f"  - exited at target (take profit):                     {targets}")
    print(f"  - exited at stop (loss):                              {stops}")
    print(f"Win rate:                                               {win_rate*100:7.2f}%")
    print(f"Average return per trade:                               {avg_ret*100:7.3f}%")
    print(f"Maximum drawdown:                                       {max_dd*100:7.2f}%")

    print("\nTrade log:")
    print(f"  {'entry':>10}  {'exit':>10}  {'in':>8} {'out':>8}  {'ret%':>7}  reason")
    for t in trades:
        print(f"  {t['entry_time'].date()!s:>10}  {t['exit_time'].date()!s:>10}  "
              f"{t['entry']:>8.5f} {t['exit']:>8.5f}  {t['ret']*100:>7.2f}  {t['reason']}")

    print("\nCaveats: daily-bar intrabar fills are approximate (stop assumed hit")
    print("before target within a candle); next-open fills avoid look-ahead;")
    print("costs = live spread per side. Small trade counts make win rate noisy.")


if __name__ == "__main__":
    main()
