#!/usr/bin/env python3
"""One-off script to clear all rows from the transactions table."""

import sqlite3
from pathlib import Path


DB_PATH: Path = Path(__file__).parent.parent / "gemini_echo.db"


def clear_transactions() -> None:
    conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions")
    conn.commit()
    deleted: int = cursor.rowcount
    conn.close()
    print(f"Cleared {deleted} row(s) from transactions.")


if __name__ == "__main__":
    clear_transactions()
