#!/usr/bin/env python3

import sys
import grpc
import gemini_pb2
import gemini_pb2_grpc


def main():
    prompt = " ".join(sys.argv[1:]).strip()
    if not prompt:
        raise SystemExit("Usage: ./client.py 'your prompt'")

    with grpc.insecure_channel("localhost:50051") as channel:
        stub = gemini_pb2_grpc.GeminiServiceStub(channel)
        response = stub.Generate(gemini_pb2.GenerateRequest(prompt=prompt))
        print(response.text)


if __name__ == "__main__":
    main()