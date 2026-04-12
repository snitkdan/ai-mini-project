"""gRPC client — send a prompt and display the latest DB record."""

import sys

import grpc
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

import proto.generated.gemini_echo_pb2 as pb2
import proto.generated.gemini_echo_pb2_grpc as pb2_grpc
from logger import logger
from storage.client import DBClient
from storage.client import Transaction


GRPC_TARGET: str = "localhost:50051"

console = Console()


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
        console.print(Rule("[bold cyan]LATEST DATABASE RECORD[/bold cyan]"))
        console.print(f"[bold]ID       :[/bold] {record.id}")
        console.print(f"[bold]Timestamp:[/bold] {record.timestamp}")
        console.print(f"[bold]Prompt   :[/bold] {record.prompt}")
        console.print(Rule("[bold cyan]Response[/bold cyan]"))
        console.print(Markdown(record.response))
        console.print(Rule())

    db.close()


if __name__ == "__main__":
    main()
