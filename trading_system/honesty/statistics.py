"""Statistical honesty: sample-size warnings and a deflation for multiple testing.

Two lies this catches:
  1. Small-sample bravado — a 75% win rate on 4 trades is noise. We warn below a
     configurable trade count.
  2. Multiple-testing inflation — if you sweep 20 parameter combos and report the
     best, the headline is inflated simply because you took a max over noise. We
     apply a deflation (a conservative haircut growing with the number of trials)
     so the reported edge is discounted for how many tries it took to find it.
"""

from __future__ import annotations

import math

from ..config.settings import MIN_TRADES_FOR_CONFIDENCE


def sample_size_flags(n_trades: int) -> list[str]:
    flags = []
    if n_trades == 0:
        flags.append("NO TRADES — the rule never fired; nothing to evaluate")
    elif n_trades < 10:
        flags.append(f"TINY SAMPLE ({n_trades} trades) — this is an anecdote, not evidence")
    elif n_trades < MIN_TRADES_FOR_CONFIDENCE:
        flags.append(f"SMALL SAMPLE ({n_trades} trades) — win rate and return are statistically unreliable")
    return flags


def deflate_for_trials(best_return: float, n_trials: int, n_trades: int) -> tuple[float, str]:
    """Return (deflated_return, note). Heuristic, conservative, and clearly
    labeled as such — the goal is to puncture false confidence, not to be a
    precise p-value. Haircut grows with log(trials) and shrinks with sample size.

    With a single trial there is no deflation. With many trials over a small
    sample, the haircut is large, reflecting that the 'best of many' over noise
    is mostly luck."""
    if n_trials <= 1 or n_trades == 0:
        return best_return, "no multiple-testing deflation (single trial)"
    # Expected max of n_trials draws from noise scales ~ sqrt(2*ln(trials)).
    inflation = math.sqrt(2.0 * math.log(n_trials))
    # Per-trade noise proxy shrinks as 1/sqrt(n_trades).
    noise_per = 1.0 / math.sqrt(n_trades)
    haircut = inflation * noise_per * abs(best_return)
    deflated = best_return - math.copysign(haircut, best_return)
    note = (f"deflated for {n_trials} trials: {best_return*100:+.2f}% -> "
            f"{deflated*100:+.2f}% (haircut {haircut*100:.2f}%)")
    return deflated, note
