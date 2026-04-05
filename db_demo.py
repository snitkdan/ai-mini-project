#!/usr/bin/env python3

"""
db_demo.py

Hello-world example: define a schema and store records
in a local SQLite database using Python's built-in sqlite3.
"""

import sqlite3

DB_FILE = "data.db"


def init_db(conn: sqlite3.Connection) -> None:
    """Create the schema if it doesn't already exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT    NOT NULL
        )
    """)
    conn.commit()
    print("✔ Schema ready (table: test)")


def insert_test(conn: sqlite3.Connection, name: str) -> int:
    """Insert a test record and return the new row id."""
    cursor = conn.execute(
        "INSERT INTO test (name) VALUES (?)", (name,)
    )
    conn.commit()
    return cursor.lastrowid


def list_test(conn: sqlite3.Connection) -> None:
    """Print all records in the test table."""
    rows = conn.execute("SELECT * FROM test").fetchall()

    print(f"\n{'ID':<4} {'Name':<20}")
    print("-" * 24)
    for row in rows:
        print(f"{row[0]:<4} {row[1]:<20}")


def main() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        print(f"Hello, World! Connected to '{DB_FILE}'")

        init_db(conn)

        sample_users = [
            ("Test1",),
        ]

        for (name,) in sample_users:
            try:
                row_id = insert_test(conn, name)
                print(f"✔ Inserted: {name} (id={row_id})")
            except sqlite3.IntegrityError:
                print(f"⚠ Skipped duplicate: {name}")

        list_test(conn)

    print(f"\nDone! Data persisted in '{DB_FILE}'")


if __name__ == "__main__":
    main()