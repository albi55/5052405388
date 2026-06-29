"""Global configuration.

The single most important line in this file is EXECUTION_ENABLED. It is the
second of three independent locks that keep this build incapable of placing a
live order (the others: execution/order_gate.py raising by default, and the
absence of any validated ValidationRecord). See execution/README.md.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# THE EXECUTION LOCK.
# This build ships with execution DISABLED. Setting this to True is necessary
# but NOT sufficient to place an order: the order gate still raises, and the
# runner still requires a human-promoted ValidationRecord that does not exist
# until a strategy survives out-of-sample testing AND a multi-week demo run.
# Do not flip this without reading execution/README.md.
# --------------------------------------------------------------------------
EXECUTION_ENABLED = False

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_CACHE_DIR = PROJECT_ROOT / ".cache"
RECORDS_DB_PATH = PROJECT_ROOT / "records.sqlite"

DATA_CACHE_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------------------
# Validation defaults (the honesty layer)
# --------------------------------------------------------------------------
# Fraction of the (time-ordered) history reserved for in-sample optimization.
# The remainder is held back as out-of-sample and is structurally inaccessible
# until the strategy parameters are frozen.
DEFAULT_IN_SAMPLE_FRACTION = 0.5

# Below this trade count, results are labeled statistically unreliable.
MIN_TRADES_FOR_CONFIDENCE = 30

# Walk-forward defaults.
DEFAULT_WF_TRAIN_BARS = 750
DEFAULT_WF_TEST_BARS = 250

# Overfit thresholds.
# If in-sample return exceeds out-of-sample by more than this (absolute, as a
# fraction), flag OVERFIT.
OVERFIT_IS_OOS_GAP = 0.05
# If the optimal parameter changes across slices by more than this fraction of
# the swept range, flag parameter instability.
PARAM_INSTABILITY_TOLERANCE = 0.34
