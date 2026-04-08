"""One-off script to clear all rows from the transactions table."""

import sqlite3
from pathlib import Path

from logger import logger
from storage.schema import TABLE_NAME


DB_PATH: Path = Path(__file__).parent.parent / "gemini_echo.db"


def clear_transactions() -> None:
    conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(f"DELETE FROM #{TABLE_NAME}")
    conn.commit()
    deleted: int = cursor.rowcount
    conn.close()
    logger.info(f"Cleared {deleted} row(s) from transactions.")


if __name__ == "__main__":
    clear_transactions()
