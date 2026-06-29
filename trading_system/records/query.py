"""Convenience queries over the record store — compare runs, find what already
failed, so a dead idea isn't retested in a future session."""

from __future__ import annotations

from .store import RecordStore


def summarize_history(store: RecordStore, symbol: str | None = None) -> str:
    rows = store.list_verdicts(symbol)
    if not rows:
        return "No past research runs recorded yet."
    lines = [f"{len(rows)} past run(s)" + (f" for {symbol}" if symbol else "") + ":"]
    lines.append(f"  {'id':>4}  {'symbol':>7} {'tf':>4}  {'survives':>8}  "
                 f"{'OOS ret':>8}  {'OOS DD':>8}  {'trades':>6}  {'overfit':>7}")
    for r in rows:
        lines.append(
            f"  {r['id']:>4}  {r['symbol']:>7} {r['timeframe']:>4}  "
            f"{'YES' if r['survives'] else 'no':>8}  "
            f"{r['oos_return']*100:>7.2f}%  {r['oos_max_dd']*100:>7.2f}%  "
            f"{r['oos_trades']:>6}  {r['overfit_risk']:>7}")
    survivors = [r for r in rows if r["survives"]]
    lines.append("")
    lines.append(f"  Survived honest testing: {len(survivors)} of {len(rows)}")
    return "\n".join(lines)
