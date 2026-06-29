"""Assert the loop never selects a validation-LOSING strategy as a finalist, and
never reports an edge from a proxy strategy. These guard the two ways the loop
could lie: crowning a loser, or treating synthetic carry as real."""

import unittest

from ..search.loop import run_loop
from ..search.generator import generate
from .helpers import make_bars, sine_closes, trending_closes


class TestLoopFinalist(unittest.TestCase):
    def test_no_finalist_when_nothing_profitable_on_validation(self):
        # A purely trending series fed to mean-reversion price strategies should
        # not produce a profitable validation finalist; loop must report none.
        bars = make_bars(trending_closes(1200))
        specs = [s for s in generate(families=("price",),
                                     pairs=["EURUSD"], timeframes=["D1"])]
        for s in specs:
            s.symbol, s.timeframe = "EURUSD", "D1"
        result = run_loop(specs, {("EURUSD", "D1"): bars},
                          time_budget_s=30, min_trades=5, log=lambda *_: None)
        if result.finalist is not None:
            # if a finalist exists it MUST have been profitable on validation
            self.assertGreater(result.finalist.validation_return, 0)

    def test_proxy_finalist_never_counts_as_edge(self):
        bars = make_bars(sine_closes(1600))
        specs = generate(families=("carry",), pairs=["EURUSD"], timeframes=["D1"])
        for s in specs:
            s.symbol, s.timeframe = "EURUSD", "D1"
        result = run_loop(specs, {("EURUSD", "D1"): bars},
                          time_budget_s=30, min_trades=5, log=lambda *_: None)
        # even if a proxy carry strategy looks great, edge_found must be False
        self.assertFalse(result.edge_found)


if __name__ == "__main__":
    unittest.main()
