"""Unit tests for the GeminiEchoWorkflow using Temporal's testing framework."""

import concurrent.futures
import uuid
from collections.abc import AsyncGenerator
from collections.abc import Sequence
from typing import Any

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ActivityError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflow.workflow import GeminiEchoWorkflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def workflow_env() -> AsyncGenerator[WorkflowEnvironment]:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_CONN_ID = "fake-conn-id"


async def _run_workflow(
    env: WorkflowEnvironment,
    prompt: str,
    mock_activities: Sequence[Any],
) -> str:
    """Start and await the workflow inside the given test environment."""
    async with Worker(
        env.client,
        task_queue="test-queue",
        workflows=[GeminiEchoWorkflow],
        activities=mock_activities,
        activity_executor=concurrent.futures.ThreadPoolExecutor(),
    ):
        return await env.client.execute_workflow(
            GeminiEchoWorkflow.run,
            prompt,
            id=str(uuid.uuid4()),
            task_queue="test-queue",
        )


def make_mock_activities(
    gemini_return: str = "",
    gemini_raises: Exception | None = None,
    save_return: int = 1,
) -> list[Any]:
    """
    Build fake @activity.defn functions that share the registered names of
    the real activities. The Worker will dispatch to these instead.
    """

    @activity.defn(name="open_db_connection")
    def fake_open_db_connection() -> str:
        return _FAKE_CONN_ID

    @activity.defn(name="close_db_connection")
    def fake_close_db_connection(conn_id: str) -> None:
        _ = conn_id

    @activity.defn(name="call_gemini")
    def fake_call_gemini(prompt: str) -> str:
        _ = prompt
        if gemini_raises is not None:
            raise gemini_raises
        return gemini_return

    @activity.defn(name="save_to_db")
    def fake_save_to_db(conn_id: str, prompt: str, response: str) -> int:
        _ = (conn_id, prompt, response)
        return save_return

    return [
        fake_open_db_connection,
        fake_close_db_connection,
        fake_call_gemini,
        fake_save_to_db,
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_returns_gemini_response(
    workflow_env: WorkflowEnvironment,
) -> None:
    """Workflow returns whatever call_gemini resolves to."""
    mocks = make_mock_activities(gemini_return="mocked response")

    result = await _run_workflow(workflow_env, "test prompt", mocks)

    assert result == "mocked response"


@pytest.mark.asyncio
async def test_workflow_calls_save_with_conn_id_prompt_and_response(
    workflow_env: WorkflowEnvironment,
) -> None:
    """save_to_db is called with conn_id, original prompt, and Gemini response."""
    received: list[tuple[str, str, str]] = []

    @activity.defn(name="open_db_connection")
    def fake_open_db_connection() -> str:
        return _FAKE_CONN_ID

    @activity.defn(name="close_db_connection")
    def fake_close_db_connection(conn_id: str) -> None:
        _ = conn_id

    @activity.defn(name="call_gemini")
    def fake_call_gemini(prompt: str) -> str:
        _ = prompt
        return "gemini says hi"

    @activity.defn(name="save_to_db")
    def fake_save_to_db(conn_id: str, prompt: str, response: str) -> int:
        received.append((conn_id, prompt, response))
        return 1

    await _run_workflow(
        workflow_env,
        "original prompt",
        [
            fake_open_db_connection,
            fake_close_db_connection,
            fake_call_gemini,
            fake_save_to_db,
        ],
    )

    assert received == [(_FAKE_CONN_ID, "original prompt", "gemini says hi")]


@pytest.mark.asyncio
async def test_workflow_propagates_gemini_failure(
    workflow_env: WorkflowEnvironment,
) -> None:
    """If call_gemini raises after retries, the workflow itself fails."""
    mocks = make_mock_activities(gemini_raises=Exception("Gemini is down"))

    with pytest.raises(WorkflowFailureError) as exc_info:
        await _run_workflow(workflow_env, "any prompt", mocks)

    workflow_err = exc_info.value
    activity_err = workflow_err.cause
    assert isinstance(activity_err, ActivityError)
    cause = activity_err.cause

    assert cause is not None
    assert "Gemini is down" in str(cause)


@pytest.mark.asyncio
async def test_workflow_does_not_call_save_on_gemini_failure(
    workflow_env: WorkflowEnvironment,
) -> None:
    """save_to_db is never called if call_gemini fails."""
    save_called = False

    @activity.defn(name="open_db_connection")
    def fake_open_db_connection() -> str:
        return _FAKE_CONN_ID

    @activity.defn(name="close_db_connection")
    def fake_close_db_connection(conn_id: str) -> None:
        _ = conn_id

    @activity.defn(name="call_gemini")
    def fake_call_gemini(prompt: str) -> str:
        _ = prompt
        msg = "Gemini is down"
        raise RuntimeError(msg)

    @activity.defn(name="save_to_db")
    def fake_save_to_db(conn_id: str, prompt: str, response: str) -> int:
        _ = (conn_id, prompt, response)
        nonlocal save_called
        save_called = True
        return 1

    with pytest.raises(WorkflowFailureError):
        await _run_workflow(
            workflow_env,
            "any prompt",
            [
                fake_open_db_connection,
                fake_close_db_connection,
                fake_call_gemini,
                fake_save_to_db,
            ],
        )

    assert not save_called


@pytest.mark.asyncio
async def test_workflow_always_closes_connection_on_success(
    workflow_env: WorkflowEnvironment,
) -> None:
    """close_db_connection is called with the correct conn_id on success."""
    closed_ids: list[str] = []

    @activity.defn(name="open_db_connection")
    def fake_open_db_connection() -> str:
        return _FAKE_CONN_ID

    @activity.defn(name="close_db_connection")
    def fake_close_db_connection(conn_id: str) -> None:
        closed_ids.append(conn_id)

    @activity.defn(name="call_gemini")
    def fake_call_gemini(prompt: str) -> str:
        _ = prompt
        return "response"

    @activity.defn(name="save_to_db")
    def fake_save_to_db(conn_id: str, prompt: str, response: str) -> int:
        _ = (conn_id, prompt, response)
        return 1

    await _run_workflow(
        workflow_env,
        "prompt",
        [
            fake_open_db_connection,
            fake_close_db_connection,
            fake_call_gemini,
            fake_save_to_db,
        ],
    )

    assert closed_ids == [_FAKE_CONN_ID]


@pytest.mark.asyncio
async def test_workflow_always_closes_connection_on_gemini_failure(
    workflow_env: WorkflowEnvironment,
) -> None:
    """close_db_connection is still called even if call_gemini fails."""
    closed_ids: list[str] = []

    @activity.defn(name="open_db_connection")
    def fake_open_db_connection() -> str:
        return _FAKE_CONN_ID

    @activity.defn(name="close_db_connection")
    def fake_close_db_connection(conn_id: str) -> None:
        closed_ids.append(conn_id)

    @activity.defn(name="call_gemini")
    def fake_call_gemini(prompt: str) -> str:
        _ = prompt
        msg = "Gemini is down"
        raise RuntimeError(msg)

    @activity.defn(name="save_to_db")
    def fake_save_to_db(conn_id: str, prompt: str, response: str) -> int:
        _ = (conn_id, prompt, response)
        return 1

    with pytest.raises(WorkflowFailureError):
        await _run_workflow(
            workflow_env,
            "any prompt",
            [
                fake_open_db_connection,
                fake_close_db_connection,
                fake_call_gemini,
                fake_save_to_db,
            ],
        )

    assert closed_ids == [_FAKE_CONN_ID]
