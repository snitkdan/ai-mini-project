#!/usr/bin/env python3
"""Temporal workflow: orchestrate Gemini call → DB save."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from workflow.activities import (
        call_gemini,
        close_db_connection,
        open_db_connection,
        save_to_db,
    )

_RETRY_POLICY = RetryPolicy(maximum_attempts=3)

_GEMINI_TIMEOUT = timedelta(minutes=5)
_DB_TIMEOUT = timedelta(seconds=30)


@workflow.defn
class GeminiEchoWorkflow:
    @workflow.run
    async def run(self, prompt: str) -> str:
        conn_id: str | None = None
        try:
            conn_id = await workflow.execute_activity(
                open_db_connection,
                start_to_close_timeout=_DB_TIMEOUT,
                retry_policy=_RETRY_POLICY,
            )

            response: str = await workflow.execute_activity(
                call_gemini,
                prompt,
                start_to_close_timeout=_GEMINI_TIMEOUT,
                retry_policy=_RETRY_POLICY,
            )

            await workflow.execute_activity(
                save_to_db,
                args=[conn_id, prompt, response],
                start_to_close_timeout=_DB_TIMEOUT,
                retry_policy=_RETRY_POLICY,
            )
        finally:
            if conn_id is not None:
                await workflow.execute_activity(
                    close_db_connection,
                    conn_id,
                    start_to_close_timeout=_DB_TIMEOUT,
                    retry_policy=_RETRY_POLICY,
                )

        return response
