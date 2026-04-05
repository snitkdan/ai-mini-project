# server

gRPC server for `gemini_echo`. Accepts `GeminiEchoRequest` messages,
executes the `GeminiEchoWorkflow` synchronously via Temporal, and
returns a `GeminiEchoResponse`.

## Prerequisites

- Proto stubs compiled into `proto/generated/` (see `proto/` README).
- Temporal server running on `localhost:7233`.
- `workflow/worker.py` running (in a separate terminal).

## Running

From the **project root**:

```bash
python -m server.grpc_server
```

The server listens on `0.0.0.0:50051` (insecure).

Stop with **Ctrl-C** — shutdown is handled gracefully with a 5 s grace period.