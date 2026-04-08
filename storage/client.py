#!/usr/bin/env python3
"""SQLite client for the {TABLE_NAME} table."""

import sqlite3
from pathlib import Path

from storage.protocol import TransactionStore
from storage.schema import TABLE_NAME
from storage.schema import Transaction


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
        return Transaction(**dict(row))

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    def insert(self, prompt: str, response: str) -> int:
        """Insert a new transaction row and return the new row id."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute(
            f"""
            INSERT INTO {TABLE_NAME} (prompt, timestamp, response)
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

    def query_by_id(self, row_id: int) -> Transaction | None:
        """Return a single transaction by primary key, or None if not found."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE id = ?",
            (row_id,),
        )
        row: sqlite3.Row | None = cursor.fetchone()
        return self._row_to_transaction(row) if row is not None else None

    def list_all(self) -> list[Transaction]:
        """Return all {TABLE_NAME} ordered by id ascending."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY id ASC")
        return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def latest(self) -> Transaction | None:
        """Return the most recently inserted transaction, or None if empty."""
        cursor: sqlite3.Cursor = self._conn.cursor()
        cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY id DESC LIMIT 1")
        row: sqlite3.Row | None = cursor.fetchone()
        return self._row_to_transaction(row) if row is not None else None


# Ensure DBClient conforms to TransactionStore
_: TransactionStore = DBClient.__new__(DBClient)
