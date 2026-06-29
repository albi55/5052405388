"""Component 2 entry point — runs, but is incapable of trading in this build.

It reports execution status, lists any validation records (there are none until a
human promotes a surviving strategy through the gate), and demonstrates that an
attempted execution cycle is refused at the gate. This is the inert-but-present
face of the execution component.

Usage:
  python -m trading_system.apps.execution_cli --status
  python -m trading_system.apps.execution_cli --attempt   # will be refused
"""

from __future__ import annotations

import argparse

from ..config.settings import EXECUTION_ENABLED
from ..records.store import SQLiteRecordStore
from ..execution.runner import ExecutionRunner, MIN_DEMO_DAYS
from ..execution.order_gate import ExecutionDisabledError


def cmd_status():
    print("=" * 70)
    print("EXECUTION COMPONENT STATUS")
    print("=" * 70)
    print(f"  EXECUTION_ENABLED (build lock): {EXECUTION_ENABLED}")
    print(f"  Order gate: place_order() RAISES (locked integration point)")
    print(f"  Required for eligibility: OOS survival AND >= {MIN_DEMO_DAYS} demo days")
    records = SQLiteRecordStore().list_validation_records()
    print(f"  Promoted (eligible) strategies: {len(records)}")
    for r in records:
        print(f"    - {r['strategy_id']} (demo {r['demo_run_days']}d, by {r['promoted_by']})")
    print()
    if not EXECUTION_ENABLED and not records:
        print("  => This build CANNOT place a live order. Nothing is armed, and")
        print("     nothing has survived research + demo to be armed. By design.")
    print("=" * 70)


def cmd_attempt():
    """Demonstrate that an execution attempt is refused at the gate."""
    print("Attempting one execution cycle (expected: refused)...\n")
    # No promoted record exists, so pass None — the runner refuses at preflight.
    runner = ExecutionRunner(record=None)
    ok, reason = runner.preflight()
    print(f"  preflight ok={ok}: {reason}")
    try:
        runner.run_once("EURUSD", direction=1, volume=1000.0)
    except ExecutionDisabledError as e:
        print(f"\n  REFUSED (as designed): {e}")
        return
    print("\n  !!! UNEXPECTED: an order path executed. This must never happen in "
          "this build. Investigate immediately.")


def main():
    ap = argparse.ArgumentParser(description="Execution component (DISABLED in this build).")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--attempt", action="store_true",
                    help="try to run a cycle; it will be refused at the gate")
    args = ap.parse_args()
    if args.attempt:
        cmd_attempt()
    else:
        cmd_status()


if __name__ == "__main__":
    main()
