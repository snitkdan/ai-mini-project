#!/usr/bin/env python3
"""SQLite client for the transactions table."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DB_PATH: Path = Path(__file__).parent.parent / "gemini_echo.db"


@dataclass
class Transaction:
    id: int
    prompt: str
    timestamp: str
    response: str


class DBClient:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._db_path: Path = db_path
        self._conn: sqlite3.Connection = self._connect()

    def _connect(self) -> sqlite3.Connection:
        conn: sqlite3.Connection = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    def insert(self, prompt: str, response: str) -> int:
        """Insert a new transaction row and return the new row id."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO transactions (prompt, timestamp, response)
            VALUES (
                ?,
                strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                ?
            )
            """,
            (prompt, response),
        )
        self._conn.commit()
        row_id: int = cursor.lastrowid  # type: ignore[assignment]
        return row_id

    def query_by_id(self, row_id: int) -> Optional[Transaction]:
        """Return a single transaction by primary key, or None if not found."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, prompt, timestamp, response FROM transactions WHERE id = ?",
            (row_id,),
        )
        row: Optional[sqlite3.Row] = cursor.fetchone()
        if row is None:
            return None
        return Transaction(
            id=row["id"],
            prompt=row["prompt"],
            timestamp=row["timestamp"],
            response=row["response"],
        )

    def list_all(self) -> list[Transaction]:
        """Return all transactions ordered by id ascending."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, prompt, timestamp, response FROM transactions ORDER BY id ASC"
        )
        rows: list[sqlite3.Row] = cursor.fetchall()
        return [
            Transaction(
                id=row["id"],
                prompt=row["prompt"],
                timestamp=row["timestamp"],
                response=row["response"],
            )
            for row in rows
        ]

    def latest(self) -> Optional[Transaction]:
        """Return the most recently inserted transaction, or None if empty."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, prompt, timestamp, response FROM transactions ORDER BY id DESC LIMIT 1"
        )
        row: Optional[sqlite3.Row] = cursor.fetchone()
        if row is None:
            return None
        return Transaction(
            id=row["id"],
            prompt=row["prompt"],
            timestamp=row["timestamp"],
            response=row["response"],
        )