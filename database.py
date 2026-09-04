"""Persistencia local en SQLite: metadatos de proyectos procesados."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).parent / "projects.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    original_path TEXT NOT NULL,
    duration      REAL NOT NULL,
    sample_rate   INTEGER NOT NULL,
    channels      INTEGER NOT NULL,
    bit_depth     INTEGER NOT NULL,
    export_path   TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _connect() -> sqlite3.Connection:
    """Abre la BD garantizando el esquema (idempotente) y el cierre limpio."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def save_project(
    original_path: Path,
    duration: float,
    sample_rate: int,
    channels: int,
    bit_depth: int,
) -> int:
    with closing(_connect()) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO projects (original_path, duration, sample_rate, channels, bit_depth) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(original_path), duration, sample_rate, channels, bit_depth),
        )
        return int(cursor.lastrowid)


def set_export_path(project_id: int, export_path: Path) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE projects SET export_path = ? WHERE id = ?",
            (str(export_path), project_id),
        )


def list_projects() -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        return list(
            conn.execute("SELECT * FROM projects ORDER BY created_at DESC")
        )
