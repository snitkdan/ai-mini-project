#!/usr/bin/env python3

import asyncio
import grpc
from generated import greeter_pb2, greeter_pb2_grpc
import sys


async def main(name: str):
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = greeter_pb2_grpc.GreeterServiceStub(channel)
        response = await stub.Greet(greeter_pb2.GreetRequest(name=name))
        print(f"{response.message}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ./starter.py <name>")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))