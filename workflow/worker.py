#!/usr/bin/env python3
"""Run the Temporal worker that polls the gemini-echo task queue."""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from workflow.activities import call_gemini
from workflow.activities import close_db_connection
from workflow.activities import open_db_connection
from workflow.activities import save_to_db
from workflow.workflow import GeminiEchoWorkflow


TEMPORAL_ADDRESS: str = "localhost:7233"
TASK_QUEUE: str = "gemini-echo"


async def main() -> None:
    client: Client = await Client.connect(TEMPORAL_ADDRESS)

    worker: Worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[GeminiEchoWorkflow],
        activities=[call_gemini, open_db_connection, close_db_connection, save_to_db],
    )

    print(f"Worker started — task queue: {TASK_QUEUE!r}  server: {TEMPORAL_ADDRESS}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
