"""
SQLite persistence for RunArtifacts.

Stores the complete artifact JSON alongside indexed metadata columns
so we can query by user_id without parsing JSON every time.
"""

import sqlite3
import os
import json
from schemas import RunArtifact


DB_PATH = os.getenv("DATABASE_PATH", "edu_pipeline.db")


def _get_connection() -> sqlite3.Connection:
    """Open a connection and ensure the table exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_artifacts (
            run_id      TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            grade       INTEGER,
            topic       TEXT,
            status      TEXT,
            created_at  TEXT,
            finished_at TEXT,
            artifact_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_id
        ON run_artifacts(user_id)
    """)
    conn.commit()
    return conn


def save_artifact(artifact: RunArtifact) -> None:
    """Persist a RunArtifact to the database."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO run_artifacts
            (run_id, user_id, grade, topic, status, created_at, finished_at, artifact_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact.run_id,
                artifact.input.user_id,
                artifact.input.grade,
                artifact.input.topic,
                artifact.final.status,
                artifact.timestamps.started_at,
                artifact.timestamps.finished_at,
                artifact.model_dump_json(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_history(user_id: str) -> list:
    """Retrieve all RunArtifacts for a user, most recent first."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT artifact_json FROM run_artifacts
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        return [RunArtifact.model_validate_json(row[0]) for row in rows]
    finally:
        conn.close()
