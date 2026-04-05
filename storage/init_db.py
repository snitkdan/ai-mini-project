#!/usr/bin/env python3
"""One-off script to initialise the SQLite database and create the transactions table."""

import sqlite3
from pathlib import Path

DB_PATH: Path = Path(__file__).parent.parent / "gemini_echo.db"


def init_db() -> None:
    conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt    TEXT    NOT NULL,
            timestamp TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            response  TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print(f"Database initialised at: {DB_PATH}")


if __name__ == "__main__":
    init_db()