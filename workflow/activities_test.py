#!/usr/bin/env python3
"""Unit tests for Temporal activities."""

import pytest
import respx
import httpx
from pathlib import Path
from unittest.mock import patch, MagicMock
from workflow.activities import call_gemini, save_to_db, GEMINI_URL


# ---------------------------------------------------------------------------
# call_gemini
# ---------------------------------------------------------------------------

MOCK_GEMINI_RESPONSE = {
    "candidates": [
        {
            "content": {
                "parts": [{"text": "Hello from Gemini!"}]
            }
        }
    ]
}


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

    sent = route.calls.last.request
    import json
    body = json.loads(sent.content)
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
# save_to_db
# ---------------------------------------------------------------------------


def _make_db_client() -> "DBClient":
    """Return a DBClient backed by an in-memory SQLite instance with schema applied."""
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


@pytest.mark.asyncio
async def test_save_to_db_returns_row_id():
    """save_to_db returns a positive integer row id."""
    fake_db = _make_db_client()

    with patch("storage.client.DBClient", return_value=fake_db):
        row_id = await save_to_db("hello", "world", close_db=False)

    assert isinstance(row_id, int)
    assert row_id >= 1


@pytest.mark.asyncio
async def test_save_to_db_persists_data():
    """Prompt and response are actually written to the DB."""
    fake_db = _make_db_client()

    with patch("storage.client.DBClient", return_value=fake_db):
        row_id = await save_to_db("my prompt", "my response", close_db=False)

    row = fake_db.query_by_id(row_id)
    assert row.prompt == "my prompt"
    assert row.response == "my response"


@pytest.mark.asyncio
async def test_save_to_db_increments_row_id():
    """Each insert gets a distinct, incrementing row id."""
    fake_db = _make_db_client()

    with patch("storage.client.DBClient", return_value=fake_db):
        id1 = await save_to_db("prompt 1", "response 1", close_db=False)
        id2 = await save_to_db("prompt 2", "response 2", close_db=False)

    assert id2 > id1