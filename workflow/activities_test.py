#!/usr/bin/env python3
"""Unit tests for Temporal activities."""

import json

import httpx
import pytest
import respx
from pathlib import Path
from unittest.mock import patch

from workflow.activities import (
    _DB_REGISTRY,
    call_gemini,
    close_db_connection,
    open_db_connection,
    save_to_db,
    GEMINI_URL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_client():
    """Return a DBClient backed by an in-memory SQLite instance."""
    from storage.client import DBClient

    db = DBClient(db_path=Path(":memory:"))
    db._conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt    TEXT    NOT NULL,
            timestamp TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            response  TEXT    NOT NULL
        )
        """
    )
    db._conn.commit()
    return db


MOCK_GEMINI_RESPONSE = {
    "candidates": [{"content": {"parts": [{"text": "Hello from Gemini!"}]}}]
}


# ---------------------------------------------------------------------------
# call_gemini
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_call_gemini_returns_text():
    """Happy path: correct text is extracted from the Gemini response."""
    respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(200, json=MOCK_GEMINI_RESPONSE)
    )

    result = await call_gemini("Say hello")

    assert result == "Hello from Gemini!"


@respx.mock
@pytest.mark.asyncio
async def test_call_gemini_sends_prompt_in_body():
    """The prompt is forwarded correctly in the request payload."""
    route = respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(200, json=MOCK_GEMINI_RESPONSE)
    )

    await call_gemini("My test prompt")

    body = json.loads(route.calls.last.request.content)
    assert body["contents"][0]["parts"][0]["text"] == "My test prompt"


@respx.mock
@pytest.mark.asyncio
async def test_call_gemini_raises_on_http_error():
    """A non-2xx response causes httpx to raise."""
    respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await call_gemini("Trigger error")


# ---------------------------------------------------------------------------
# open_db_connection / close_db_connection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_db_connection_registers_client():
    """open_db_connection returns a UUID string and adds an entry to the registry."""
    fake_db = _make_db_client()

    with patch("storage.client.DBClient", return_value=fake_db):
        conn_id = await open_db_connection()

    try:
        assert isinstance(conn_id, str) and len(conn_id) == 36  # UUID format
        assert _DB_REGISTRY[conn_id] is fake_db
    finally:
        _DB_REGISTRY.pop(conn_id, None)


@pytest.mark.asyncio
async def test_close_db_connection_deregisters_and_closes():
    """close_db_connection closes the client and removes it from the registry."""
    fake_db = _make_db_client()
    conn_id = "test-conn-id"
    _DB_REGISTRY[conn_id] = fake_db

    with patch.object(fake_db, "close") as mock_close:
        await close_db_connection(conn_id)

    mock_close.assert_called_once()
    assert conn_id not in _DB_REGISTRY


@pytest.mark.asyncio
async def test_close_db_connection_unknown_id_is_noop():
    """Closing an unrecognised connection id does not raise."""
    await close_db_connection("nonexistent-id")  # should not raise


# ---------------------------------------------------------------------------
# save_to_db
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_to_db_returns_row_id():
    """save_to_db returns a positive integer row id."""
    fake_db = _make_db_client()
    conn_id = "test-conn-id"
    _DB_REGISTRY[conn_id] = fake_db

    try:
        row_id = await save_to_db(conn_id, "hello", "world")
        assert isinstance(row_id, int) and row_id >= 1
    finally:
        _DB_REGISTRY.pop(conn_id, None)


@pytest.mark.asyncio
async def test_save_to_db_persists_data():
    """Prompt and response are actually written to the DB."""
    fake_db = _make_db_client()
    conn_id = "test-conn-id"
    _DB_REGISTRY[conn_id] = fake_db

    try:
        row_id = await save_to_db(conn_id, "my prompt", "my response")
        row = fake_db.query_by_id(row_id)
        assert row.prompt == "my prompt"
        assert row.response == "my response"
    finally:
        _DB_REGISTRY.pop(conn_id, None)


@pytest.mark.asyncio
async def test_save_to_db_increments_row_id():
    """Each insert gets a distinct, incrementing row id."""
    fake_db = _make_db_client()
    conn_id = "test-conn-id"
    _DB_REGISTRY[conn_id] = fake_db

    try:
        id1 = await save_to_db(conn_id, "prompt 1", "response 1")
        id2 = await save_to_db(conn_id, "prompt 2", "response 2")
        assert id2 > id1
    finally:
        _DB_REGISTRY.pop(conn_id, None)


@pytest.mark.asyncio
async def test_save_to_db_raises_on_missing_connection():
    """save_to_db raises RuntimeError when the conn_id is not registered."""
    with pytest.raises(RuntimeError, match="No DB connection found"):
        await save_to_db("ghost-id", "prompt", "response")