#!/usr/bin/env python3
"""SQLite client for the transactions table."""

import sqlite3
from pathlib import Path
from typing import Optional

from storage.schema import CREATE_TABLE_SQL, Transaction
from storage.protocol import TransactionStore

# Re-export so existing `from storage.client import Transaction` imports still work.
__all__ = ["DBClient", "Transaction", "TransactionStore"]

DB_PATH: Path = Path(__file__).parent.parent / "gemini_echo.db"


class DBClient:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._db_path: Path = db_path
        self._conn: sqlite3.Connection = self._connect()

    def _connect(self) -> sqlite3.Connection:
        conn: sqlite3.Connection = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_transaction(self, row: sqlite3.Row) -> Transaction:
        return Transaction(**{k: row[k] for k in row.keys()})

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
            "SELECT * FROM transactions WHERE id = ?",
            (row_id,),
        )
        row: Optional[sqlite3.Row] = cursor.fetchone()
        return self._row_to_transaction(row) if row is not None else None

    def list_all(self) -> list[Transaction]:
        """Return all transactions ordered by id ascending."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM transactions ORDER BY id ASC")
        return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def latest(self) -> Optional[Transaction]:
        """Return the most recently inserted transaction, or None if empty."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 1")
        row: Optional[sqlite3.Row] = cursor.fetchone()
        return self._row_to_transaction(row) if row is not None else None
