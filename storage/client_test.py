"""Tests for storage/client.py"""

from collections.abc import Generator
from pathlib import Path

import pytest

from storage.client import DBClient
from storage.client import Transaction
from storage.protocol import TransactionStore
from storage.schema import CREATE_TABLE_SQL


@pytest.fixture
def client() -> Generator[DBClient]:
    db = DBClient(db_path=Path(":memory:"))
    db._conn.execute(CREATE_TABLE_SQL)
    db._conn.commit()
    yield db
    db.close()


# --- protocol ---


def test_dbclient_satisfies_protocol(client: DBClient) -> None:
    assert isinstance(client, TransactionStore)


# --- insert / query_by_id ---


def test_insert_and_query_by_id(client: DBClient) -> None:
    row_id = client.insert("hello", "world")
    result = client.query_by_id(row_id)

    assert isinstance(result, Transaction)
    assert result.id == row_id
    assert result.prompt == "hello"
    assert result.response == "world"
    assert result.timestamp  # non-empty ISO string


def test_query_by_id_missing_returns_none(client: DBClient) -> None:
    assert client.query_by_id(999) is None


# --- list_all ---


def test_list_all_returns_ordered_transactions(client: DBClient) -> None:
    client.insert("first", "resp_a")
    client.insert("second", "resp_b")
    results = client.list_all()

    assert len(results) == 2
    assert results[0].prompt == "first"
    assert results[1].prompt == "second"


def test_list_all_empty_returns_empty_list(client: DBClient) -> None:
    assert client.list_all() == []


# --- latest ---


def test_latest_returns_most_recent(client: DBClient) -> None:
    client.insert("older", "resp_a")
    client.insert("newer", "resp_b")

    result = client.latest()

    assert result is not None
    assert result.prompt == "newer"


def test_latest_empty_returns_none(client: DBClient) -> None:
    assert client.latest() is None
