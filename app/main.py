import os

import grpc
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import proto.generated.gemini_echo_pb2 as pb2
import proto.generated.gemini_echo_pb2_grpc as pb2_grpc


GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50051")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_methods=["*"],
    allow_headers=["*"],
)

channel = grpc.insecure_channel(GRPC_TARGET)
stub = pb2_grpc.GeminiEchoServerStub(channel)


class PromptRequest(BaseModel):
    prompt: str


class PromptResponse(BaseModel):
    response: str


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/prompt", response_model=PromptResponse)
def prompt(req: PromptRequest) -> dict[str, str]:
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    try:
        result = stub.Echo(
            pb2.GeminiEchoRequest(prompt=req.prompt),
            timeout=30,
        )
    except grpc.RpcError as e:
        code = e.code()
        if code == grpc.StatusCode.UNAVAILABLE:
            raise HTTPException(
                status_code=503, detail="gRPC service unavailable"
            ) from e
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            raise HTTPException(status_code=504, detail="gRPC timeout") from e
        if code == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=400, detail=e.details()) from e
        raise HTTPException(status_code=500, detail=e.details()) from e
    else:
        return {"response": result.output}
