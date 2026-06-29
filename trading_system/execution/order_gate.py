"""⛔ THE LOCKED DOOR — the single integration point for live order placement.

In this build, place_order() RAISES. It is the first of three independent locks
(see execution/README.md). This file is intentionally tiny and obvious so that
arming live trading is a deliberate, reviewable act and can never happen by
accident or as a side effect of some other change.

When (and only when) a strategy has survived honest OOS testing AND a multi-week
demo run, the real broker call is implemented at the clearly marked point below,
shaped around that specific validated strategy.
"""

from __future__ import annotations

from ..config.settings import EXECUTION_ENABLED


class ExecutionDisabledError(RuntimeError):
    """Raised by place_order() in any build where live execution is not armed."""


def place_order(symbol: str, direction: int, volume: float, *, broker=None,
                metadata: dict | None = None):
    """Place a live order. DISABLED IN THIS BUILD.

    Three conditions must ALL be satisfied before this may place a real order:
      1. EXECUTION_ENABLED is True (config/settings.py)
      2. the real broker logic below is implemented (currently absent)
      3. the caller (runner) has verified an eligible ValidationRecord

    Today, condition 2 is absent and condition 1 is False, so this always raises.
    """
    # ----- LOCK 1 of 3: hard guard ---------------------------------------
    if not EXECUTION_ENABLED:
        raise ExecutionDisabledError(
            "Live execution is DISABLED in this build (EXECUTION_ENABLED=False). "
            "No validated strategy exists to arm it. See execution/README.md."
        )

    # ----- SINGLE INTEGRATION POINT (intentionally not implemented) ------
    # When arming a validated strategy, implement the real broker order here,
    # shaped around that strategy's sizing/risk rules. Until then, this raises so
    # that flipping EXECUTION_ENABLED alone is still not enough to trade.
    raise ExecutionDisabledError(
        "No live order implementation present. This is the marked integration "
        "point; it must be implemented deliberately for a specific validated "
        "strategy. Refusing to place a real-money order."
    )
