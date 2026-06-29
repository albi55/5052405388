"""Assert this build is incapable of placing a live order. These are the most
important tests in the project: if any fails, the safety guarantee is broken."""

import unittest

from ..config.settings import EXECUTION_ENABLED
from ..execution.order_gate import place_order, ExecutionDisabledError
from ..execution.runner import ExecutionRunner
from ..core.types import ValidationRecord


class TestExecutionDisabled(unittest.TestCase):
    def test_build_lock_is_off(self):
        self.assertFalse(EXECUTION_ENABLED,
                         "EXECUTION_ENABLED must be False in this build")

    def test_place_order_raises(self):
        with self.assertRaises(ExecutionDisabledError):
            place_order("EURUSD", 1, 1000.0)

    def test_runner_without_record_refuses(self):
        runner = ExecutionRunner(record=None)
        ok, _ = runner.preflight()
        self.assertFalse(ok)
        with self.assertRaises(ExecutionDisabledError):
            runner.run_once("EURUSD", 1, 1000.0)

    def test_runner_even_with_eligible_record_still_cannot_trade(self):
        """Even if someone forged an 'eligible' record, EXECUTION_ENABLED is False
        and the order gate raises — defense in depth means no single bypass works."""
        rec = ValidationRecord(
            strategy_id="forged", spec_json="{}", oos_survived=True,
            oos_verdict_id=1, demo_run_started="2026-01-01", demo_run_days=999,
            promoted_by="test", promoted_at="2026-01-01",
        )
        runner = ExecutionRunner(record=rec)
        with self.assertRaises(ExecutionDisabledError):
            runner.run_once("EURUSD", 1, 1000.0)


if __name__ == "__main__":
    unittest.main()
