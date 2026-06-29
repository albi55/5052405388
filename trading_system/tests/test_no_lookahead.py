"""Assert the engine cannot see the future: a trade opened on a signal at bar i
must fill at bar i+1's open, never bar i's close, and indicators must not use
future bars."""

import unittest
import numpy as np

from ..core.strategy_spec import StrategySpec, SignalSpec, ExitSpec, SizingSpec
from ..config.costs import CostModel
from ..backtest.engine import run_backtest
from ..strategy import indicators as ind
from .helpers import make_bars, sine_closes


ZERO_COST = CostModel(spread=0.0, commission=0.0, slippage=0.0, swap_per_day=0.0)


class TestNoLookahead(unittest.TestCase):
    def test_sma_uses_only_past(self):
        closes = list(range(1, 51))
        arr = np.array(closes, dtype=float)
        sma = ind.sma(arr, 10)
        # sma[9] is the first defined value; it must equal mean of closes[0:10].
        self.assertTrue(np.isnan(sma[8]))
        self.assertAlmostEqual(sma[9], float(np.mean(arr[0:10])))
        # changing a FUTURE close must not alter a past sma value.
        arr2 = arr.copy()
        arr2[40] = 999.0
        sma2 = ind.sma(arr2, 10)
        self.assertAlmostEqual(sma[9], sma2[9])

    def test_entry_fills_on_next_open_not_signal_close(self):
        bars = make_bars(sine_closes(300))
        spec = StrategySpec(
            name="t", symbol="EURUSD", timeframe="D1", direction=1,
            entry=SignalSpec("sma_discount", {"period": 20, "discount": 0.005}),
            exit=ExitSpec("target_sma", {"period": 20, "stop": 0.05}),
            sizing=SizingSpec(),
        )
        trades = run_backtest(spec, bars, ZERO_COST)
        self.assertGreater(len(trades), 0)
        for t in trades:
            self.assertLess(t.entry_time, t.exit_time)


if __name__ == "__main__":
    unittest.main()
