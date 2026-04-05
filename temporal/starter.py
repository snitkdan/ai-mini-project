#!/usr/bin/env python3

import asyncio
import grpc
from generated import greeter_pb2, greeter_pb2_grpc


async def main():
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = greeter_pb2_grpc.GreeterServiceStub(channel)
        response = await stub.Greet(greeter_pb2.GreetRequest(name="Temporal"))
        print(f"Result: {response.message}")


asyncio.run(main())