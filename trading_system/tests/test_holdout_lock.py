"""Assert the three-way split's final holdout is locked until commit, and that a
single split cannot be fished (commit is single-use)."""

import unittest

from ..honesty.holdout import ThreeWaySplit, HoldoutLockedError
from ..search.loop import multiple_testing_haircut
from .helpers import make_bars, sine_closes


class TestHoldoutLock(unittest.TestCase):
    def setUp(self):
        self.bars = make_bars(sine_closes(800))

    def test_holdout_locked_before_commit(self):
        split = ThreeWaySplit(self.bars)
        # train and validation are free
        self.assertGreater(len(split.train), 0)
        self.assertGreater(len(split.validation), 0)
        # holdout raises until committed
        with self.assertRaises(HoldoutLockedError):
            split.holdout()

    def test_holdout_available_after_commit(self):
        split = ThreeWaySplit(self.bars)
        split.commit_final("strat-A")
        self.assertGreater(len(split.holdout()), 0)

    def test_commit_is_single_use(self):
        split = ThreeWaySplit(self.bars)
        split.commit_final("strat-A")
        with self.assertRaises(HoldoutLockedError):
            split.commit_final("strat-B")   # cannot fish a second finalist

    def test_partitions_are_time_ordered(self):
        split = ThreeWaySplit(self.bars)
        split.commit_final("x")
        spans = split.spans()
        self.assertLessEqual(spans["train"][1], spans["validation"][1])
        self.assertLessEqual(spans["validation"][1], spans["holdout"][1])

    def test_haircut_deflates_and_never_inflates(self):
        # more trials => bigger haircut; haircut reduces magnitude toward zero
        r = 0.10
        d1 = multiple_testing_haircut(r, n_strategies=2, n_trades=40)
        d100 = multiple_testing_haircut(r, n_strategies=100, n_trades=40)
        self.assertLess(d1, r)
        self.assertLess(d100, d1)
        # single trial => no deflation
        self.assertEqual(multiple_testing_haircut(r, 1, 40), r)


if __name__ == "__main__":
    unittest.main()
