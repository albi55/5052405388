"""Assert the cost floor cannot be bypassed: resolve_cost() never returns a
spread below the instrument floor, even when the live spread is 0 or None."""

import unittest

from ..config.costs import resolve_cost, floor_for


class TestCostFloor(unittest.TestCase):
    def test_zero_live_spread_uses_floor(self):
        cost = resolve_cost("EURUSD", 0.0)
        self.assertGreaterEqual(cost.spread, floor_for("EURUSD").spread)
        self.assertGreater(cost.per_side(), 0.0)

    def test_none_live_spread_uses_floor(self):
        cost = resolve_cost("EURUSD", None)
        self.assertGreaterEqual(cost.spread, floor_for("EURUSD").spread)

    def test_larger_live_spread_is_respected(self):
        big = floor_for("EURUSD").spread * 5
        cost = resolve_cost("EURUSD", big)
        self.assertAlmostEqual(cost.spread, big)

    def test_unknown_symbol_has_nonzero_floor(self):
        cost = resolve_cost("XYZABC", 0.0)
        self.assertGreater(cost.per_side(), 0.0)


if __name__ == "__main__":
    unittest.main()
