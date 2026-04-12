"""Temporal workflow: orchestrate Gemini call -> DB save."""

from __future__ import annotations

from datetime import timedelta
from typing import cast

from temporalio import workflow
from temporalio.common import RetryPolicy


_RETRY_POLICY = RetryPolicy(maximum_attempts=3)

_GEMINI_TIMEOUT = timedelta(minutes=5)
_DB_TIMEOUT = timedelta(seconds=30)


@workflow.defn
class GeminiEchoWorkflow:
    @workflow.run
    async def run(self, prompt: str) -> str:  # noqa: PLR6301
        conn_id: str | None = None
        response = ""

        try:
            conn_id = cast(
                "str",
                await workflow.execute_activity(
                    "open_db_connection",
                    start_to_close_timeout=_DB_TIMEOUT,
                    retry_policy=_RETRY_POLICY,
                ),
            )

            response = cast(
                "str",
                await workflow.execute_activity(
                    "call_gemini",
                    prompt,
                    start_to_close_timeout=_GEMINI_TIMEOUT,
                    retry_policy=_RETRY_POLICY,
                ),
            )

            await workflow.execute_activity(
                "save_to_db",
                args=[conn_id, prompt, response],
                start_to_close_timeout=_DB_TIMEOUT,
                retry_policy=_RETRY_POLICY,
            )
        finally:
            if conn_id is not None:
                await workflow.execute_activity(
                    "close_db_connection",
                    conn_id,
                    start_to_close_timeout=_DB_TIMEOUT,
                    retry_policy=_RETRY_POLICY,
                )

        return response
