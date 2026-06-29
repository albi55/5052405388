"""Assert out-of-sample data is structurally locked until freeze(), and freeze()
is single-use so you cannot re-tune after peeking."""

import unittest

from ..honesty.split import DataSplit, OutOfSampleLockedError
from .helpers import make_bars, sine_closes


class TestOOSPeekPrevention(unittest.TestCase):
    def setUp(self):
        self.bars = make_bars(sine_closes(400))

    def test_oos_locked_before_freeze(self):
        split = DataSplit(self.bars, in_sample_fraction=0.5)
        self.assertGreater(len(split.in_sample), 0)
        with self.assertRaises(OutOfSampleLockedError):
            split.out_of_sample()

    def test_oos_available_after_freeze(self):
        split = DataSplit(self.bars, in_sample_fraction=0.5)
        split.freeze({"entry.params.discount": 0.01})
        self.assertGreater(len(split.out_of_sample()), 0)

    def test_freeze_is_single_use(self):
        split = DataSplit(self.bars, in_sample_fraction=0.5)
        split.freeze({"a": 1})
        with self.assertRaises(OutOfSampleLockedError):
            split.freeze({"a": 2})

    def test_split_is_time_ordered(self):
        split = DataSplit(self.bars, in_sample_fraction=0.5)
        split.freeze({})
        in_end = split.in_sample[-1].time
        oos_start, _ = split.out_of_sample_span()
        self.assertLessEqual(in_end, oos_start)


if __name__ == "__main__":
    unittest.main()
