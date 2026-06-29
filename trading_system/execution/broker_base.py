"""Abstract broker interface for the (future) execution component. No concrete
implementation ships in this build — a live broker adapter would implement this,
and even then every order routes through order_gate.place_order(), which is
locked. Defining the interface now keeps the execution architecture complete and
makes the eventual demo-first adapter a drop-in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Broker(ABC):
    @abstractmethod
    def account_equity(self) -> float: ...

    @abstractmethod
    def open_positions(self) -> list: ...

    @abstractmethod
    def submit(self, symbol: str, direction: int, volume: float, metadata: dict) -> dict:
        """Submit an order. A real implementation MUST route through
        order_gate.place_order(), never call a broker API directly, so the lock
        cannot be bypassed."""
        ...
