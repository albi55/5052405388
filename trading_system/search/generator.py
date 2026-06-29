"""Strategy generator for the autonomous loop. Enumerates candidate StrategySpecs
across families, instruments, timeframes, and parameters.

Two families:
  PRICE-ONLY  (sma_discount, zscore, rsi, breakout) — fully honest on real MT5
              data, but our evidence says this family is likely a dead end
              (RANDOM WALK). The loop will most often confirm 'nothing survives'.
  CARRY       (rate_differential) — the one family the random-walk diagnostic
              does NOT condemn, because it is not price-predicting-price. Requires
              a rate-differential series; until a real feed is wired, results are
              labeled proxy-only and are NOT tradeable evidence.

Each generated spec carries its own internal parameter sweep (optimized on TRAIN
inside the honest pipeline). The generator controls the OUTER search (which
specs exist at all); that outer count is what the multiple-testing correction
deflates against.
"""

from __future__ import annotations

from ..core.strategy_spec import StrategySpec, SignalSpec, ExitSpec, SizingSpec


# Conservative default universe. Expand freely — the loop's correction scales
# with however many specs this produces.
DEFAULT_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]
DEFAULT_TIMEFRAMES = ["D1", "H4"]


def _price_specs(pairs, timeframes):
    specs = []
    for sym in pairs:
        for tf in timeframes:
            # sma_discount with an inner discount sweep
            specs.append(StrategySpec(
                name=f"sma_dip_{sym}_{tf}", symbol=sym, timeframe=tf, direction=1,
                entry=SignalSpec("sma_discount", {"period": 20, "discount": 0.01}),
                exit=ExitSpec("target_sma", {"period": 20, "stop": 0.03}),
                sizing=SizingSpec(),
                sweep={"entry.params.discount": [0.005, 0.01, 0.015, 0.02]},
            ))
            # zscore (volatility-scaled dip) with a k sweep
            specs.append(StrategySpec(
                name=f"zscore_{sym}_{tf}", symbol=sym, timeframe=tf, direction=1,
                entry=SignalSpec("zscore", {"period": 20, "k": 2.0}),
                exit=ExitSpec("atr_trailing", {"atr_period": 14, "atr_mult": 2.0}),
                sizing=SizingSpec(),
                sweep={"entry.params.k": [1.5, 2.0, 2.5]},
            ))
            # rsi oversold with a level sweep
            specs.append(StrategySpec(
                name=f"rsi_{sym}_{tf}", symbol=sym, timeframe=tf, direction=1,
                entry=SignalSpec("rsi", {"period": 14, "level": 30}),
                exit=ExitSpec("atr_trailing", {"atr_period": 14, "atr_mult": 2.0}),
                sizing=SizingSpec(),
                sweep={"entry.params.level": [25, 30, 35]},
            ))
            # breakout (momentum, not reversion) with a lookback sweep
            specs.append(StrategySpec(
                name=f"breakout_{sym}_{tf}", symbol=sym, timeframe=tf, direction=1,
                entry=SignalSpec("breakout", {"period": 20}),
                exit=ExitSpec("atr_trailing", {"atr_period": 14, "atr_mult": 3.0}),
                sizing=SizingSpec(),
                sweep={"entry.params.period": [10, 20, 40]},
            ))
    return specs


def _carry_specs(pairs, timeframes):
    specs = []
    for sym in pairs:
        for tf in timeframes:
            specs.append(StrategySpec(
                name=f"carry_{sym}_{tf}", symbol=sym, timeframe=tf, direction=1,
                entry=SignalSpec("rate_differential", {"level": 0.0}),
                exit=ExitSpec("time", {"bars": 20}),
                sizing=SizingSpec(),
                sweep={"entry.params.level": [0.0, 0.5, 1.0]},
            ))
    return specs


def generate(families=("price", "carry"),
             pairs=None, timeframes=None) -> list[StrategySpec]:
    pairs = pairs or DEFAULT_PAIRS
    timeframes = timeframes or DEFAULT_TIMEFRAMES
    specs = []
    if "price" in families:
        specs += _price_specs(pairs, timeframes)
    if "carry" in families:
        specs += _carry_specs(pairs, timeframes)
    return specs
