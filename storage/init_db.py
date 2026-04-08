#!/usr/bin/env python3
"""One-off script to initialise the db + transactions table"""

import sqlite3
from pathlib import Path

from logger import logger
from storage.schema import CREATE_TABLE_SQL
from storage.schema import TABLE_NAME


DB_PATH: Path = Path(__file__).parent.parent / "gemini_echo.db"


def init_db() -> None:
    conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    conn.close()
    logger.info(f"Database initialised at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
