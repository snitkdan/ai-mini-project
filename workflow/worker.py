from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from logger import logger
from workflow.activities import Activities
from workflow.constants import TASK_QUEUE
from workflow.observability import BraintrustDeps
from workflow.workflow import GeminiEchoWorkflow


async def main() -> None:
    client = await Client.connect("localhost:7233")

    activities = Activities(observability=BraintrustDeps())

    with ThreadPoolExecutor(max_workers=10) as activity_executor:
        worker = Worker(
            client,
            task_queue=TASK_QUEUE,
            workflows=[GeminiEchoWorkflow],
            activities=[
                activities.open_db_connection,
                activities.close_db_connection,
                activities.call_gemini,
                activities.save_to_db,
            ],
            activity_executor=activity_executor,
        )

        logger.info("Worker started")
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
