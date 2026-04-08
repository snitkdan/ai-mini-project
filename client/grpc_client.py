"""gRPC client — send a prompt and display the latest DB record."""

import sys

import grpc

import proto.generated.gemini_echo_pb2 as pb2
import proto.generated.gemini_echo_pb2_grpc as pb2_grpc
from logger import logger
from storage.client import DBClient
from storage.client import Transaction


GRPC_TARGET: str = "localhost:50051"


def main() -> None:
    if len(sys.argv) != 2:
        logger.error('Usage: python -m client.grpc_client "<prompt>"')
        sys.exit(1)

    prompt: str = sys.argv[1]

    with grpc.insecure_channel(GRPC_TARGET) as channel:
        stub: pb2_grpc.GeminiEchoServerStub = pb2_grpc.GeminiEchoServerStub(channel)
        request: pb2.GeminiEchoRequest = pb2.GeminiEchoRequest(prompt=prompt)
        stub.Echo(request)

    db: DBClient = DBClient()
    record: Transaction | None = db.latest()

    if record is not None:
        logger.info("=" * 60)
        logger.info("LATEST DATABASE RECORD")
        logger.info("=" * 60)
        logger.info("  ID        : %s", record.id)
        logger.info("  Timestamp : %s", record.timestamp)
        logger.info("  Prompt    : %s", record.prompt)
        logger.info("  Response  : %s", record.response)
        logger.info("=" * 60)

    db.close()


if __name__ == "__main__":
    main()
