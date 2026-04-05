#!/usr/bin/env python3

import os
import grpc
import requests
import signal
from concurrent import futures
from dotenv import load_dotenv

import gemini_pb2
import gemini_pb2_grpc

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("Set GEMINI_API_KEY")

MODEL = "gemini-2.5-flash"
URL = (
    f"https://generativelanguage.googleapis.com"
    f"/v1beta/models/{MODEL}:generateContent"
)


class GeminiServicer(gemini_pb2_grpc.GeminiServiceServicer):
    def Generate(self, request, context):
        if not request.prompt:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "prompt is required")

        print(f"processing prompt: ${request.prompt}")
        payload = {
            "contents": [{"parts": [{"text": request.prompt}]}]
        }

        try:
            resp = requests.post(
                URL,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": API_KEY,
                },
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Gemini API error: #{e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Gemini API error: {e}")

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return gemini_pb2.GenerateResponse(text=text)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    gemini_pb2_grpc.add_GeminiServiceServicer_to_server(GeminiServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC server listening on port 50051")
    
    def handle_shutdown(sig, frame):
        print("\nShutting down gracefully...")
        server.stop(grace=5).wait()
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()