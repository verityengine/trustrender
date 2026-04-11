"""Stage-by-stage render lineage persistence.

Records what happened at each pipeline stage during a render: what was
checked, what passed, what failed, how long it took. No raw data stored —
only hashes, timings, stage outcomes, and metadata.

Storage is SQLite, append-only. Opt-in via ``TRUSTRENDER_HISTORY`` env var
or ``history`` parameter.

Usage::

    from trustrender.trace import TraceStore

    store = TraceStore("~/.trustrender/history.db")
    store.record(trace)

    for event in store.query(template="invoice.j2.typ", limit=20):
        print(event.outcome, event.total_ms)
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StageTrace:
    """Trace of a single pipeline stage."""

    stage: str  # "zugferd_validation", "contract_validation", "compilation", etc.
    status: str  # "pass", "fail", "skip", "error"
    duration_ms: int = 0
    checks_run: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    errors: list[dict] = field(default_factory=list)  # [{path, message}]
    metadata: dict = field(default_factory=dict)  # stage-specific info


@dataclass
class RenderTrace:
    """Complete lineage record for one render execution."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    template_name: str = ""
    template_hash: str = ""
    data_hash: str = ""
    outcome: str = ""  # "success" or "error"
    error_code: str = ""
    error_stage: str = ""
    error_message: str = ""
    total_ms: int = 0
    pdf_size: int = 0
    engine_version: str = ""
    backend: str = ""
    zugferd_profile: str = ""
    provenance_hash: str = ""
    output_hash: str = ""  # SHA-256 of final PDF bytes (after all post-processing)
    validated: bool = False
    stages: list[StageTrace] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> RenderTrace:
        stages = [StageTrace(**s) for s in d.pop("stages", [])]
        return cls(**d, stages=stages)


# ---------------------------------------------------------------------------
# SQLite store
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS render_traces (
    id              TEXT PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    template_name   TEXT NOT NULL,
    template_hash   TEXT,
    data_hash       TEXT,
    outcome         TEXT NOT NULL,
    error_code      TEXT,
    error_stage     TEXT,
    error_message   TEXT,
    total_ms        INTEGER,
    pdf_size        INTEGER,
    engine_version  TEXT,
    backend         TEXT,
    zugferd_profile TEXT,
    provenance_hash TEXT,
    output_hash     TEXT DEFAULT '',
    validated       BOOLEAN,
    stages_json     TEXT
);

CREATE INDEX IF NOT EXISTS idx_traces_ts ON render_traces(timestamp);
CREATE INDEX IF NOT EXISTS idx_traces_template ON render_traces(template_name);
CREATE INDEX IF NOT EXISTS idx_traces_outcome ON render_traces(outcome);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_version (version, applied_at)
VALUES (1, datetime('now'));
"""


class TraceStore:
    """Append-only SQLite store for render lineage traces."""

    def __init__(self, db_path: str | os.PathLike):
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            # Migration: add output_hash column to existing databases
            try:
                conn.execute("ALTER TABLE render_traces ADD COLUMN output_hash TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # Column already exists

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, trace: RenderTrace) -> None:
        """Persist a render trace. Append-only, never updates."""
        stages_json = json.dumps([asdict(s) for s in trace.stages], separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO render_traces (
                    id, timestamp, template_name, template_hash, data_hash,
                    outcome, error_code, error_stage, error_message,
                    total_ms, pdf_size, engine_version, backend,
                    zugferd_profile, provenance_hash, output_hash, validated, stages_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace.id,
                    trace.timestamp,
                    trace.template_name,
                    trace.template_hash,
                    trace.data_hash,
                    trace.outcome,
                    trace.error_code,
                    trace.error_stage,
                    trace.error_message,
                    trace.total_ms,
                    trace.pdf_size,
                    trace.engine_version,
                    trace.backend,
                    trace.zugferd_profile,
                    trace.provenance_hash,
                    trace.output_hash,
                    trace.validated,
                    stages_json,
                ),
            )

    def query(
        self,
        *,
        template: str | None = None,
        outcome: str | None = None,
        since: str | None = None,
        limit: int = 20,
    ) -> list[RenderTrace]:
        """Query render traces with optional filters."""
        where_clauses = []
        params: list[Any] = []

        if template:
            where_clauses.append("template_name = ?")
            params.append(template)
        if outcome:
            where_clauses.append("outcome = ?")
            params.append(outcome)
        if since:
            where_clauses.append("timestamp >= ?")
            params.append(since)

        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"SELECT * FROM render_traces {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        traces = []
        for row in rows:
            stages = json.loads(row["stages_json"] or "[]")
            traces.append(RenderTrace(
                id=row["id"],
                timestamp=row["timestamp"],
                template_name=row["template_name"],
                template_hash=row["template_hash"] or "",
                data_hash=row["data_hash"] or "",
                outcome=row["outcome"],
                error_code=row["error_code"] or "",
                error_stage=row["error_stage"] or "",
                error_message=row["error_message"] or "",
                total_ms=row["total_ms"] or 0,
                pdf_size=row["pdf_size"] or 0,
                engine_version=row["engine_version"] or "",
                backend=row["backend"] or "",
                zugferd_profile=row["zugferd_profile"] or "",
                provenance_hash=row["provenance_hash"] or "",
                output_hash=row["output_hash"] if "output_hash" in row.keys() else "",
                validated=bool(row["validated"]),
                stages=[StageTrace(**s) for s in stages],
            ))
        return traces

    def get(self, trace_id: str) -> RenderTrace | None:
        """Get a single trace by ID."""
        results = self.query(limit=1)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM render_traces WHERE id = ?", (trace_id,)
            ).fetchone()
        if not row:
            return None
        stages = json.loads(row["stages_json"] or "[]")
        return RenderTrace(
            id=row["id"],
            timestamp=row["timestamp"],
            template_name=row["template_name"],
            template_hash=row["template_hash"] or "",
            data_hash=row["data_hash"] or "",
            outcome=row["outcome"],
            error_code=row["error_code"] or "",
            error_stage=row["error_stage"] or "",
            error_message=row["error_message"] or "",
            total_ms=row["total_ms"] or 0,
            pdf_size=row["pdf_size"] or 0,
            engine_version=row["engine_version"] or "",
            backend=row["backend"] or "",
            zugferd_profile=row["zugferd_profile"] or "",
            provenance_hash=row["provenance_hash"] or "",
            output_hash=row["output_hash"] if "output_hash" in row.keys() else "",
            validated=bool(row["validated"]),
            stages=[StageTrace(**s) for s in stages],
        )

    def stats(self, since: str | None = None) -> dict:
        """Aggregate statistics."""
        where = f"WHERE timestamp >= '{since}'" if since else ""
        with self._connect() as conn:
            row = conn.execute(f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
                    SUM(CASE WHEN outcome = 'error' THEN 1 ELSE 0 END) as failures,
                    AVG(total_ms) as avg_ms,
                    COUNT(DISTINCT template_name) as unique_templates
                FROM render_traces {where}
            """).fetchone()
        total = row["total"] or 0
        successes = row["successes"] or 0
        return {
            "total": total,
            "successes": successes,
            "failures": row["failures"] or 0,
            "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
            "avg_ms": round(row["avg_ms"] or 0),
            "unique_templates": row["unique_templates"] or 0,
        }


# ---------------------------------------------------------------------------
# Global store (opt-in)
# ---------------------------------------------------------------------------

_store: TraceStore | None = None


def get_store() -> TraceStore | None:
    """Get the global trace store, or None if history is not enabled."""
    global _store
    if _store is not None:
        return _store

    history_path = os.environ.get("TRUSTRENDER_HISTORY")
    if not history_path:
        return None

    if history_path == "1":
        history_path = os.path.expanduser("~/.trustrender/history.db")

    _store = TraceStore(history_path)
    return _store


def init_store(path: str | os.PathLike) -> TraceStore:
    """Explicitly initialize the global trace store."""
    global _store
    _store = TraceStore(path)
    return _store


