"""Three-way split for AUTOMATED search — the anti-overfitting upgrade.

The two-way split (honesty/split.py) protects a SINGLE strategy test. It does NOT
protect "best of N automated tests": if a loop tries 800 strategies and reports
the best out-of-sample one, that winner is probably luck — the same way the best
of 800 coin-flippers looks skilled. Searching at scale needs a THIRD partition
that NOTHING optimizes against, touched exactly once, for the final candidate
only — plus a haircut for how many strategies were tried.

Partitions (time-ordered, never random):
  TRAIN      (in-sample)      — optimize parameters here, freely.
  VALIDATION (out-of-sample)  — rank/select strategies here. The loop sees this a
                                lot, so by the end it is "soft-contaminated" by
                                selection — which is exactly why we keep a third.
  HOLDOUT    (final)          — LOCKED. Readable only after a strategy is chosen
                                AND committed. The loop never ranks on it. Each
                                strategy may touch it at most once.

This module is deliberately strict: HOLDOUT raises until commit_final(), and the
loop engine is built so the holdout is read once per finalist, never in the
ranking step.
"""

from __future__ import annotations

from ..core.types import Bar


class HoldoutLockedError(RuntimeError):
    pass


class ThreeWaySplit:
    def __init__(self, bars: list[Bar], train_frac: float = 0.5,
                 validation_frac: float = 0.25, warmup: int = 50):
        if not (0.2 <= train_frac <= 0.8):
            raise ValueError("train_frac out of range")
        if not (0.1 <= validation_frac <= 0.4):
            raise ValueError("validation_frac out of range")
        if train_frac + validation_frac >= 0.95:
            raise ValueError("must leave a meaningful holdout (>=5%)")

        n = len(bars)
        self._a = int(n * train_frac)
        self._b = int(n * (train_frac + validation_frac))
        self._warmup = min(warmup, self._a, self._b - self._a)

        self._train = bars[: self._a]
        self._validation = bars[self._a - self._warmup: self._b]
        self._holdout_full = bars[self._b - self._warmup:]

        self._committed = False
        self._committed_strategy = None

    # ---- freely available partitions -------------------------------------
    @property
    def train(self) -> list[Bar]:
        return self._train

    @property
    def validation(self) -> list[Bar]:
        """The loop ranks strategies on this. Allowed, but by the end of a big
        search it is selection-contaminated — hence the locked holdout."""
        return self._validation

    @property
    def warmup(self) -> int:
        return self._warmup

    # ---- the locked final holdout ----------------------------------------
    def commit_final(self, strategy_id: str) -> None:
        """Commit the single chosen finalist. Single-use per split: you cannot
        keep trying finalists against the holdout until one passes (that would
        re-contaminate it). One finalist, one look."""
        if self._committed:
            raise HoldoutLockedError(
                "holdout already committed to a finalist — a fresh ThreeWaySplit is "
                "required for another finalist (prevents fishing the holdout)")
        self._committed = True
        self._committed_strategy = strategy_id

    @property
    def committed_strategy(self) -> str | None:
        return self._committed_strategy

    def holdout(self) -> list[Bar]:
        if not self._committed:
            raise HoldoutLockedError(
                "final holdout is LOCKED. Rank strategies on validation, choose ONE "
                "finalist, commit_final(id), THEN read holdout — once.")
        return self._holdout_full

    def spans(self):
        def span(seg, skip=0):
            s = seg[skip:]
            return (s[0].time, s[-1].time) if s else (None, None)
        return {
            "train": span(self._train),
            "validation": span(self._validation, self._warmup),
            "holdout": span(self._holdout_full, self._warmup),
        }
