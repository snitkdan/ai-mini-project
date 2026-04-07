#!/usr/bin/env python3
"""One-off script to initialise the SQLite database and create the transactions table."""

import sqlite3
from pathlib import Path

from storage.schema import CREATE_TABLE_SQL

DB_PATH: Path = Path(__file__).parent.parent / "gemini_echo.db"


def init_db() -> None:
    conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    conn.close()
    print(f"Database initialised at: {DB_PATH}")


if __name__ == "__main__":
    init_db()