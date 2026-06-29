"""Risk-limit framework for the (future) execution component. Fully implemented
as a structure — it computes and enforces limits — but it guards a runner whose
order path is disabled, so it cannot actually restrain live trades yet. It is
here so that when execution is armed, the limits exist from day one, not bolted
on later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_position_notional: float = 10_000.0
    max_open_positions: int = 1
    max_total_exposure: float = 10_000.0
    max_daily_loss: float = 200.0          # auto-halt threshold (account currency)
    kill_switch: bool = False              # hard stop, set manually or on breach


class RiskState:
    """Tracks live exposure/PnL and enforces limits. The (future) runner consults
    this BEFORE any order; a breach trips the kill switch and halts."""

    def __init__(self, limits: RiskLimits):
        self.limits = limits
        self.open_positions = 0
        self.total_exposure = 0.0
        self.realized_pnl_today = 0.0
        self.halted = False

    def check_can_open(self, notional: float) -> tuple[bool, str]:
        if self.limits.kill_switch or self.halted:
            return False, "halted (kill switch active)"
        if self.open_positions >= self.limits.max_open_positions:
            return False, "max open positions reached"
        if notional > self.limits.max_position_notional:
            return False, "position notional exceeds limit"
        if self.total_exposure + notional > self.limits.max_total_exposure:
            return False, "total exposure limit exceeded"
        if self.realized_pnl_today <= -abs(self.limits.max_daily_loss):
            self.halted = True
            return False, "daily loss limit breached — auto-halt"
        return True, "ok"

    def trip_kill_switch(self, reason: str = "manual"):
        self.limits.kill_switch = True
        self.halted = True
        return f"KILL SWITCH TRIPPED: {reason}"
