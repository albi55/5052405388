"""Out-of-sample enforcement with structural peek-prevention.

The defining feature of the product. A DataSplit holds the full history but
exposes the IN-SAMPLE bars freely while keeping the OUT-OF-SAMPLE bars behind a
locked method. You can only obtain the OOS bars AFTER calling freeze() with the
chosen parameters — and freeze() can be called exactly once. This makes "peeking
at out-of-sample to tune" not merely discouraged but structurally awkward: the
data isn't reachable until you've committed.

Split is TIME-ORDERED, never random — a random split leaks the future into the
past for time series. Out-of-sample carries a warm-up tail of the in-sample data
so the first OOS signal uses a fully formed indicator (no cold start, no leak:
warm-up bars feed indicators only, they are not traded because trading begins
after them).
"""

from __future__ import annotations

from ..core.types import Bar
from ..config.settings import DEFAULT_IN_SAMPLE_FRACTION


class OutOfSampleLockedError(RuntimeError):
    pass


class DataSplit:
    def __init__(self, bars: list[Bar], in_sample_fraction: float = DEFAULT_IN_SAMPLE_FRACTION,
                 warmup: int = 50):
        if not 0.1 <= in_sample_fraction <= 0.9:
            raise ValueError("in_sample_fraction must be in [0.1, 0.9]")
        n = len(bars)
        self._mid = int(n * in_sample_fraction)
        self._warmup = min(warmup, self._mid)
        self._in_sample = bars[: self._mid]
        # OOS includes a warm-up tail from in-sample for indicator formation.
        self._out_of_sample_full = bars[self._mid - self._warmup:]
        self._frozen = False
        self._frozen_params = None

    @property
    def in_sample(self) -> list[Bar]:
        """Freely accessible — this is the data you optimize on."""
        return self._in_sample

    @property
    def in_sample_span(self):
        return (self._in_sample[0].time, self._in_sample[-1].time)

    @property
    def warmup(self) -> int:
        return self._warmup

    def freeze(self, frozen_params: dict) -> None:
        """Commit the parameters. Must be called before out-of-sample is readable.
        Single-use: a second call raises, so you can't re-tune after peeking."""
        if self._frozen:
            raise OutOfSampleLockedError("split already frozen — cannot re-tune after commit")
        self._frozen = True
        self._frozen_params = dict(frozen_params)

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    @property
    def frozen_params(self) -> dict | None:
        return dict(self._frozen_params) if self._frozen_params else None

    def out_of_sample(self) -> list[Bar]:
        """LOCKED until freeze(). Returns OOS bars including the warm-up tail;
        the engine ignores trades during warm-up because indicators are NaN there
        and the first real signal occurs after the tail."""
        if not self._frozen:
            raise OutOfSampleLockedError(
                "out-of-sample data is locked until freeze(frozen_params) is called. "
                "Optimize on in_sample, freeze the winner, THEN read out_of_sample.")
        return self._out_of_sample_full

    def out_of_sample_span(self):
        traded = self._out_of_sample_full[self._warmup:]
        return (traded[0].time, traded[-1].time) if traded else (None, None)
