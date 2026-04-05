#!/usr/bin/env python3

import asyncio
from temporalio.client import Client
from workflow import GreetingWorkflow

async def main():
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        GreetingWorkflow.run,
        "World",
        id="greeting-workflow-1",
        task_queue="greeting-queue",
    )
    print(f"Result: {result}")


asyncio.run(main())