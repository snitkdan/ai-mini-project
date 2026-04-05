#!/usr/bin/env python3

import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from workflow import GreetingWorkflow, say_hello


async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="greeting-queue",
        workflows=[GreetingWorkflow],
        activities=[say_hello],
    )
    print("Worker started. Press Ctrl+C to stop.")
    await worker.run()


try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Worker stopped.")