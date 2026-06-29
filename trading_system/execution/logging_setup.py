"""Audit logging for the execution component. Comprehensive by design: in a live
system every decision (signal seen, risk check, order attempt, halt) must be
traceable. Wired up now so the scaffold logs its own refusal to trade.
"""

from __future__ import annotations

import logging

from ..config.settings import PROJECT_ROOT

_LOG_PATH = PROJECT_ROOT / "execution_audit.log"


def get_audit_logger() -> logging.Logger:
    logger = logging.getLogger("execution.audit")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(_LOG_PATH)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    return logger
