"""Execution runner — consumes a validated strategy and would run it live. In
this build it does NOT, and cannot, place orders:

  * It refuses to run without an ELIGIBLE ValidationRecord (the third lock).
    No eligible record can exist until a strategy survives OOS + a demo run, and
    only a human running gate/promote.py can create one. Research never does.
  * Even with a record, every order routes through order_gate.place_order(),
    which raises (the first lock), and EXECUTION_ENABLED is False (the second).

This file demonstrates the demo-first path and the human-in-the-loop gate without
being able to trade real money.
"""

from __future__ import annotations

from ..core.types import ValidationRecord
from ..config.settings import EXECUTION_ENABLED
from .risk_limits import RiskLimits, RiskState
from .order_gate import place_order, ExecutionDisabledError
from .logging_setup import get_audit_logger

# Minimum demo days a ValidationRecord must carry to be eligible.
MIN_DEMO_DAYS = 14


class ExecutionRunner:
    def __init__(self, record: ValidationRecord | None, limits: RiskLimits | None = None):
        self.record = record
        self.risk = RiskState(limits or RiskLimits())
        self.log = get_audit_logger()

    def preflight(self) -> tuple[bool, str]:
        """All conditions that must hold before this runner could place ANY order.
        Returns (ok, reason). In this build it always returns False."""
        if not EXECUTION_ENABLED:
            return False, "EXECUTION_ENABLED is False (build-level lock)"
        if self.record is None:
            return False, "no ValidationRecord — strategy not promoted through the gate"
        if not self.record.is_eligible(MIN_DEMO_DAYS):
            return False, ("ValidationRecord not eligible: requires OOS survival AND "
                           f">= {MIN_DEMO_DAYS} demo days")
        return True, "preflight ok"

    def run_once(self, symbol: str, direction: int, volume: float):
        """Attempt one execution cycle. Guarded and audited; in this build it logs
        the refusal and raises rather than trading."""
        ok, reason = self.preflight()
        self.log.info("preflight: ok=%s reason=%s", ok, reason)
        if not ok:
            raise ExecutionDisabledError(f"runner preflight failed: {reason}")

        can, why = self.risk.check_can_open(volume)
        self.log.info("risk check: can_open=%s reason=%s", can, why)
        if not can:
            raise ExecutionDisabledError(f"risk limits block order: {why}")

        # Even past every gate, this routes through the locked order function.
        return place_order(symbol, direction, volume, metadata={"via": "runner"})
