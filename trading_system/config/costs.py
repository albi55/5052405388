"""Per-instrument cost floors.

A backtester that models zero cost is a more sophisticated way to lie. We learned
this directly: the live MT5 spread came back as 0.0 on a closed market, which
would have modeled free trading. Every cost here is a FLOOR — the engine uses
max(live_spread, floor), never the raw live value, and never zero.

Costs are expressed in PRICE units (not points) for clarity at the call site.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    """All values in price units, charged per side unless noted."""
    spread: float          # half-the-bid/ask, charged on entry AND exit
    commission: float      # per side, in price units
    slippage: float        # adverse fill buffer per side
    swap_per_day: float    # overnight financing per day held (can be +/-)

    def per_side(self) -> float:
        """Total adverse cost applied to each fill (entry and exit)."""
        return self.spread + self.commission + self.slippage


# Realistic floors for common instruments. Conservative on purpose.
# 1 pip on a 5-digit FX major = 0.0001.
_DEFAULT_FLOORS = {
    "EURUSD": CostModel(spread=0.00010, commission=0.00002, slippage=0.00002, swap_per_day=0.00001),
    "GBPUSD": CostModel(spread=0.00012, commission=0.00002, slippage=0.00002, swap_per_day=0.00001),
    "USDJPY": CostModel(spread=0.012,   commission=0.002,   slippage=0.002,   swap_per_day=0.001),
    "AUDUSD": CostModel(spread=0.00012, commission=0.00002, slippage=0.00002, swap_per_day=0.00001),
}

# Fallback for instruments we don't have a tuned floor for: 1.5 bps of a ~1.0
# price, deliberately not tiny so unknown instruments aren't flattered.
_GENERIC_FLOOR = CostModel(spread=0.00015, commission=0.00003, slippage=0.00003, swap_per_day=0.00001)


def floor_for(symbol: str) -> CostModel:
    return _DEFAULT_FLOORS.get(symbol.upper(), _GENERIC_FLOOR)


def resolve_cost(symbol: str, live_spread_price: float | None) -> CostModel:
    """Combine a (possibly zero / missing) live spread with the floor.

    Returns a CostModel whose spread is max(live, floor.spread). This is the
    single chokepoint that makes zero-cost backtests impossible by accident.
    """
    floor = floor_for(symbol)
    live = live_spread_price if (live_spread_price and live_spread_price > 0) else 0.0
    effective_spread = max(live, floor.spread)
    return CostModel(
        spread=effective_spread,
        commission=floor.commission,
        slippage=floor.slippage,
        swap_per_day=floor.swap_per_day,
    )
