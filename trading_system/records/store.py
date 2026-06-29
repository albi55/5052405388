"""Persistent record of every research run — so you can compare across sessions
and NEVER FORGET PAST FAILURES (the whole point: most people retest dead ideas).

Backed by SQLite for v1. The RecordStore interface is deliberately narrow so the
implementation can be swapped for Supabase/Postgres later without touching
callers — the product's records table maps 1:1 onto save_verdict().
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod


def _json_safe(obj):
    """Fallback encoder: coerce numpy scalars (and anything with .item()) to
    native Python so persisted verdicts never fail to serialize."""
    if hasattr(obj, "item"):
        return obj.item()
    raise TypeError(f"not JSON serializable: {type(obj).__name__}")

from ..core.types import Verdict, ValidationRecord
from ..config.settings import RECORDS_DB_PATH


class RecordStore(ABC):
    @abstractmethod
    def save_verdict(self, spec_json: str, verdict: Verdict) -> int: ...
    @abstractmethod
    def list_verdicts(self, symbol: str | None = None) -> list[dict]: ...
    @abstractmethod
    def get_verdict(self, verdict_id: int) -> dict | None: ...
    @abstractmethod
    def save_validation_record(self, rec: ValidationRecord) -> int: ...
    @abstractmethod
    def list_validation_records(self) -> list[dict]: ...


class SQLiteRecordStore(RecordStore):
    def __init__(self, path=RECORDS_DB_PATH):
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS verdicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                symbol TEXT,
                timeframe TEXT,
                survives INTEGER,
                overfit_risk TEXT,
                oos_return REAL,
                oos_max_dd REAL,
                oos_trades INTEGER,
                regime_note TEXT,
                spec_json TEXT,
                verdict_json TEXT
            );
            CREATE TABLE IF NOT EXISTS validation_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT,
                oos_survived INTEGER,
                oos_verdict_id INTEGER,
                demo_run_started TEXT,
                demo_run_days INTEGER,
                promoted_by TEXT,
                promoted_at TEXT,
                spec_json TEXT,
                notes TEXT
            );
            """
        )
        self._conn.commit()

    def save_verdict(self, spec_json: str, verdict: Verdict) -> int:
        cur = self._conn.execute(
            """INSERT INTO verdicts (created_at, symbol, timeframe, survives,
               overfit_risk, oos_return, oos_max_dd, oos_trades, regime_note,
               spec_json, verdict_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (verdict.created_at, verdict.symbol, verdict.timeframe,
             int(verdict.survives), verdict.overfit_risk.value,
             verdict.out_of_sample.total_return, verdict.out_of_sample.max_drawdown,
             verdict.out_of_sample.n_trades, verdict.regime_note,
             spec_json, json.dumps(verdict.to_dict(), default=_json_safe)),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_verdicts(self, symbol: str | None = None) -> list[dict]:
        if symbol:
            rows = self._conn.execute(
                "SELECT * FROM verdicts WHERE symbol=? ORDER BY id DESC", (symbol,))
        else:
            rows = self._conn.execute("SELECT * FROM verdicts ORDER BY id DESC")
        return [dict(r) for r in rows.fetchall()]

    def get_verdict(self, verdict_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM verdicts WHERE id=?", (verdict_id,)).fetchone()
        return dict(row) if row else None

    def save_validation_record(self, rec: ValidationRecord) -> int:
        cur = self._conn.execute(
            """INSERT INTO validation_records (strategy_id, oos_survived,
               oos_verdict_id, demo_run_started, demo_run_days, promoted_by,
               promoted_at, spec_json, notes) VALUES (?,?,?,?,?,?,?,?,?)""",
            (rec.strategy_id, int(rec.oos_survived), rec.oos_verdict_id,
             rec.demo_run_started, rec.demo_run_days, rec.promoted_by,
             rec.promoted_at, rec.spec_json, rec.notes),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_validation_records(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM validation_records ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self._conn.close()
