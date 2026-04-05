#!/usr/bin/env python3
"""gRPC client — send a prompt and display the latest DB record."""

import sys
import grpc
import proto.generated.gemini_echo_pb2 as pb2
import proto.generated.gemini_echo_pb2_grpc as pb2_grpc
from storage.client import DBClient, Transaction

GRPC_TARGET: str = "localhost:50051"

def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m client.grpc_client \"<prompt>\"")
        sys.exit(1)

    prompt: str = sys.argv[1]

    with grpc.insecure_channel(GRPC_TARGET) as channel:
        stub: pb2_grpc.GeminiEchoServerStub = pb2_grpc.GeminiEchoServerStub(channel)
        request: pb2.GeminiEchoRequest = pb2.GeminiEchoRequest(prompt=prompt)
        stub.Echo(request)

    db: DBClient = DBClient()
    record: Transaction | None = db.latest()

    if record is not None:
        print("=" * 60)
        print("LATEST DATABASE RECORD")
        print("=" * 60)
        print(f"  ID        : {record.id}")
        print(f"  Timestamp : {record.timestamp}")
        print(f"  Prompt    : {record.prompt}")
        print(f"  Response  : {record.response}")
        print("=" * 60)


if __name__ == "__main__":
    main()