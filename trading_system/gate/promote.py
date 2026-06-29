"""THE MANUAL VALIDATION GATE — the deliberate, human-in-the-loop step between
research and execution. Research NEVER auto-promotes; this script is the ONLY way
a ValidationRecord comes into existence, and it must be run by a human who
attests to both conditions:

  (a) the strategy survived out-of-sample testing in Component 1, and
  (b) it has been demo-run for a multi-week period.

The gate enforces these mechanically: it loads the referenced verdict from the
record store and refuses to promote if survives=False, and it requires a demo
start date and day count that clears the minimum. There is intentionally no
function anywhere else in the codebase that creates a ValidationRecord.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from ..core.types import ValidationRecord
from ..records.store import SQLiteRecordStore
from ..execution.runner import MIN_DEMO_DAYS


def promote(verdict_id: int, demo_started: str, demo_days: int, promoted_by: str,
            notes: str = "") -> ValidationRecord:
    store = SQLiteRecordStore()
    verdict_row = store.get_verdict(verdict_id)
    if verdict_row is None:
        raise SystemExit(f"no verdict with id {verdict_id} — nothing to promote")

    # Condition (a): the verdict must have survived honest OOS testing.
    if not verdict_row["survives"]:
        raise SystemExit(
            f"REFUSED: verdict {verdict_id} did NOT survive out-of-sample testing "
            f"(survives=0). The gate will not promote a strategy with no OOS edge.")

    # Condition (b): a real demo run of sufficient length.
    if demo_days < MIN_DEMO_DAYS:
        raise SystemExit(
            f"REFUSED: demo run is {demo_days} days; the gate requires "
            f">= {MIN_DEMO_DAYS} days of demo trading before promotion.")

    rec = ValidationRecord(
        strategy_id=f"verdict-{verdict_id}",
        spec_json=verdict_row["spec_json"],
        oos_survived=True,
        oos_verdict_id=verdict_id,
        demo_run_started=demo_started,
        demo_run_days=demo_days,
        promoted_by=promoted_by,
        promoted_at=datetime.now(timezone.utc).isoformat(),
        notes=notes,
    )
    store.save_validation_record(rec)
    return rec


def main():
    ap = argparse.ArgumentParser(
        description="Manually promote a SURVIVING, DEMO-RUN strategy to execution "
                    "eligibility. Human-in-the-loop; research never does this.")
    ap.add_argument("--verdict-id", type=int, required=True,
                    help="id of a verdict in the record store that survived OOS")
    ap.add_argument("--demo-started", required=True,
                    help="ISO date the demo run began, e.g. 2026-06-01")
    ap.add_argument("--demo-days", type=int, required=True,
                    help=f"days the strategy ran on demo (>= {MIN_DEMO_DAYS})")
    ap.add_argument("--by", required=True, help="your name — who is attesting")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    rec = promote(args.verdict_id, args.demo_started, args.demo_days, args.by, args.notes)
    print("PROMOTED. ValidationRecord created:")
    print(json.dumps({
        "strategy_id": rec.strategy_id,
        "oos_verdict_id": rec.oos_verdict_id,
        "demo_run_days": rec.demo_run_days,
        "promoted_by": rec.promoted_by,
        "promoted_at": rec.promoted_at,
    }, indent=2))
    print("\nNOTE: execution is still disabled at the build level "
          "(EXECUTION_ENABLED=False) and the order gate still raises. Promotion "
          "is necessary but not sufficient to trade — by design.")


if __name__ == "__main__":
    main()
