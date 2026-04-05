#!/usr/bin/env python3

import asyncio
import sys
import grpc
from temporalio.client import Client
from generated import greeter_pb2, greeter_pb2_grpc
from workflow import GreetingWorkflow


class GreeterServicer(greeter_pb2_grpc.GreeterServiceServicer):
    def __init__(self, temporal_client: Client):
        self.temporal_client = temporal_client

    async def Greet(self, request, context):
        print(f"Got a greet request: {request}")
        result = await self.temporal_client.execute_workflow(
            GreetingWorkflow.run,
            request.name,
            id=f"greeting-{request.name}",
            task_queue="greeting-queue",
        )
        return greeter_pb2.GreetResponse(message=result)


async def main():
    temporal_client = await Client.connect("localhost:7233")

    server = grpc.aio.server()
    greeter_pb2_grpc.add_GreeterServiceServicer_to_server(
        GreeterServicer(temporal_client), server
    )
    server.add_insecure_port("[::]:50051")

    await server.start()
    print("gRPC server started on port 50051. Press Ctrl+C to stop.")

    try:
        await server.wait_for_termination()
    finally:
        await server.stop(grace=5)
        print("gRPC server stopped.")


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass