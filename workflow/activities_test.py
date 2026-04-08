#!/usr/bin/env python3
"""Unit tests for Temporal activities."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from storage.client import DBClient
from workflow.activities import _DB_REGISTRY
from workflow.activities import call_gemini
from workflow.activities import close_db_connection
from workflow.activities import open_db_connection
from workflow.activities import save_to_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_client() -> DBClient:
    """Return a DBClient backed by an in-memory SQLite instance."""
    from storage.client import DBClient

    db = DBClient(db_path=Path(":memory:"))
    db._conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt    TEXT    NOT NULL,
            timestamp TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            response  TEXT    NOT NULL
        )
        """)
    db._conn.commit()
    return db


def _fake_llm(response: str = "Hello from Gemini!") -> FakeListChatModel:
    return FakeListChatModel(responses=[response])


# ---------------------------------------------------------------------------
# call_gemini
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_gemini_returns_text() -> None:
    """Happy path: correct text is returned from the chain."""
    with patch("workflow.activities.ChatGoogleGenerativeAI", return_value=_fake_llm()):
        result = await call_gemini("Say hello")

    assert result == "Hello from Gemini!"


@pytest.mark.asyncio
async def test_call_gemini_sends_prompt_in_body() -> None:
    """The prompt is forwarded correctly through the chain."""
    captured: dict[str, Any] = {}
    original = FakeListChatModel._generate

    def capturing_generate(
        self: FakeListChatModel, messages: Any, **kwargs: Any
    ) -> Any:
        captured["messages"] = messages
        return original(self, messages, **kwargs)

    with patch("workflow.activities.ChatGoogleGenerativeAI", return_value=_fake_llm()):
        with patch.object(FakeListChatModel, "_generate", capturing_generate):
            await call_gemini("My test prompt")

    assert "My test prompt" in captured["messages"][-1].content


@pytest.mark.asyncio
async def test_call_gemini_raises_on_llm_error() -> None:
    """An exception from the LLM propagates out of call_gemini."""
    with patch("workflow.activities.ChatGoogleGenerativeAI", return_value=_fake_llm()):
        with patch.object(
            FakeListChatModel,
            "_generate",
            side_effect=RuntimeError("LLM unavailable"),
        ):
            with pytest.raises(RuntimeError, match="LLM unavailable"):
                await call_gemini("Trigger error")


# ---------------------------------------------------------------------------
# open_db_connection / close_db_connection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_db_connection_registers_client() -> None:
    """open_db_connection returns a UUID and adds an entry to the registry."""
    fake_db = _make_db_client()

    with patch("workflow.activities.DBClient") as MockDBClient:
        MockDBClient.return_value = fake_db
        conn_id = await open_db_connection()

    try:
        assert len(conn_id) == 36
        assert _DB_REGISTRY[conn_id] is fake_db
    finally:
        _DB_REGISTRY.pop(conn_id, None)


@pytest.mark.asyncio
async def test_close_db_connection_deregisters_and_closes() -> None:
    """close_db_connection closes the client and removes it from the registry."""
    fake_db = _make_db_client()
    conn_id = "test-conn-id"
    _DB_REGISTRY[conn_id] = fake_db

    with patch.object(fake_db, "close") as mock_close:
        await close_db_connection(conn_id)

    mock_close.assert_called_once()
    assert conn_id not in _DB_REGISTRY


@pytest.mark.asyncio
async def test_close_db_connection_unknown_id_is_noop() -> None:
    """Closing an unrecognised connection id does not raise."""
    await close_db_connection("nonexistent-id")


# ---------------------------------------------------------------------------
# save_to_db
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_to_db_returns_row_id() -> None:
    """save_to_db returns a positive integer row id."""
    fake_db = _make_db_client()
    conn_id = "test-conn-id"
    _DB_REGISTRY[conn_id] = fake_db

    try:
        row_id = await save_to_db(conn_id, "hello", "world")
        assert row_id >= 1
    finally:
        _DB_REGISTRY.pop(conn_id, None)


@pytest.mark.asyncio
async def test_save_to_db_persists_data() -> None:
    """Prompt and response are actually written to the DB."""
    fake_db = _make_db_client()
    conn_id = "test-conn-id"
    _DB_REGISTRY[conn_id] = fake_db

    try:
        row_id = await save_to_db(conn_id, "my prompt", "my response")
        row = fake_db.query_by_id(row_id)
        assert row is not None
        assert row.prompt == "my prompt"
        assert row.response == "my response"
    finally:
        _DB_REGISTRY.pop(conn_id, None)


@pytest.mark.asyncio
async def test_save_to_db_increments_row_id() -> None:
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
async def test_save_to_db_raises_on_missing_connection() -> None:
    """save_to_db raises RuntimeError when the conn_id is not registered."""
    with pytest.raises(RuntimeError, match="No DB connection found"):
        await save_to_db("ghost-id", "prompt", "response")
