"""Position sizing. Returns the notional to deploy per trade. v1 keeps this
simple and unleveraged; the point of the research tool is to isolate whether the
RULE has edge, separate from money management. Volatility scaling is provided so
risk-per-trade can be normalized when comparing strategies.
"""

from __future__ import annotations


def notional_for(sizing_spec, equity: float, atr_at_entry: float | None,
                 price: float) -> float:
    t = sizing_spec.type
    p = sizing_spec.params

    if t == "fixed_notional":
        return float(p.get("notional", 10_000.0))

    if t == "fixed_fractional":
        frac = float(p.get("fraction", 0.1))
        return equity * frac

    if t == "volatility_scaled":
        # Target a fixed fractional risk; size so that an ATR-sized adverse move
        # equals risk_fraction of equity. Falls back to fixed if ATR missing.
        risk_fraction = float(p.get("risk_fraction", 0.01))
        if atr_at_entry and atr_at_entry > 0 and price > 0:
            risk_per_unit = atr_at_entry / price          # fractional move per ATR
            return (equity * risk_fraction) / risk_per_unit
        return float(p.get("notional", 10_000.0))

    raise ValueError(f"unknown sizing type: {t}")
