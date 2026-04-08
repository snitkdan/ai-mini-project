#!/usr/bin/env python3
"""gRPC server that synchronously executes the GeminiEchoWorkflow."""

import asyncio
import uuid

import grpc
from temporalio.client import Client

import proto.generated.gemini_echo_pb2 as pb2
import proto.generated.gemini_echo_pb2_grpc as pb2_grpc
from workflow.workflow import GeminiEchoWorkflow


TEMPORAL_ADDRESS: str = "localhost:7233"
TASK_QUEUE: str = "gemini-echo"
GRPC_PORT: str = "[::]:50051"


class GeminiEchoServicer(pb2_grpc.GeminiEchoServerServicer):
    def __init__(self, temporal_client: Client) -> None:
        self._client: Client = temporal_client

    async def Echo(
        self,
        request: pb2.GeminiEchoRequest,
        context: grpc.aio.ServicerContext,  # type: ignore[type-arg]
    ) -> pb2.GeminiEchoResponse:
        workflow_id: str = f"gemini-echo-{uuid.uuid4()}"
        output: str = await self._client.execute_workflow(
            GeminiEchoWorkflow.run,
            request.prompt,
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        print(f"[server] workflow {workflow_id} completed.")
        return pb2.GeminiEchoResponse(output=output)


async def serve() -> None:
    temporal_client: Client = await Client.connect(TEMPORAL_ADDRESS)

    server: grpc.aio.Server = grpc.aio.server()
    pb2_grpc.add_GeminiEchoServerServicer_to_server(
        GeminiEchoServicer(temporal_client), server
    )
    server.add_insecure_port(GRPC_PORT)

    await server.start()
    print(f"gRPC server listening on {GRPC_PORT}")

    async def _shutdown() -> None:
        print("\nShutting down gRPC server…")
        await server.stop(grace=5)

    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    loop.add_signal_handler(
        __import__("signal").SIGINT, lambda: asyncio.ensure_future(_shutdown())
    )
    loop.add_signal_handler(
        __import__("signal").SIGTERM, lambda: asyncio.ensure_future(_shutdown())
    )

    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
