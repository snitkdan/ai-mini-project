"""Single source of truth for the transactions schema and its dataclass."""

from dataclasses import dataclass

CREATE_TABLE_SQL: str = """
    CREATE TABLE IF NOT EXISTS transactions (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt    TEXT    NOT NULL,
        timestamp TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        response  TEXT    NOT NULL
    )
"""


@dataclass
class Transaction:
    id: int
    prompt: str
    timestamp: str
    response: str
