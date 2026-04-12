from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from workflow.activities import Activities
from workflow.observability import NoopDeps


if TYPE_CHECKING:
    from langchain_core.callbacks import BaseCallbackHandler

    from storage.client import DBClient


class FakeDBClient:
    def __init__(self) -> None:
        self.closed = False
        self.rows: list[tuple[str, str]] = []

    def insert(self, prompt: str, response: str) -> int:
        self.rows.append((prompt, response))
        return len(self.rows)

    def close(self) -> None:
        self.closed = True


class FakeDeps:
    @staticmethod
    def init() -> None:
        pass

    @staticmethod
    def make_callback_handler() -> BaseCallbackHandler | None:
        return None


def test_open_and_close_db_connection() -> None:
    activities = Activities(observability=NoopDeps())

    fake_db = FakeDBClient()

    with patch("workflow.activities.DBClient", return_value=fake_db):
        conn_id = activities.open_db_connection()
        assert conn_id in activities.db_registry

        activities.close_db_connection(conn_id)
        assert conn_id not in activities.db_registry
        assert fake_db.closed is True


def test_save_to_db() -> None:
    activities = Activities(observability=NoopDeps())

    conn_id = "conn-1"
    fake_db = FakeDBClient()
    activities.db_registry[conn_id] = cast("DBClient", fake_db)

    row_id = activities.save_to_db(
        conn_id=conn_id,
        prompt="hello",
        response="world",
    )

    assert row_id == 1
    assert fake_db.rows == [("hello", "world")]


def test_save_to_db_missing_connection_raises() -> None:
    activities = Activities(observability=NoopDeps())

    with pytest.raises(RuntimeError, match="No DB connection found"):
        activities.save_to_db("missing", "hello", "world")


def test_call_gemini_uses_injected_observability() -> None:
    deps = FakeDeps()
    activities = Activities(observability=deps)

    fake_agent = SimpleNamespace(
        invoke=Mock(
            return_value={
                "messages": [
                    SimpleNamespace(content="mocked response"),
                ]
            }
        )
    )

    with (
        patch("workflow.activities.load_dotenv"),
        patch("workflow.activities.ChatGoogleGenerativeAI"),
        patch("workflow.activities.create_agent", return_value=fake_agent),
    ):
        result = activities.call_gemini("hello")

    assert result == "mocked response"
