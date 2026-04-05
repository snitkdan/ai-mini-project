#!/usr/bin/env python3

from datetime import timedelta
from temporalio import workflow

@workflow.defn
class GreetingWorkflow:
    @workflow.run
    async def run(self, prompt: str) -> str:
        return await workflow.execute_activity(
            "say_hello",
            prompt,
            start_to_close_timeout=timedelta(seconds=60),
        )