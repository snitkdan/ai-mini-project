# gemini-echo

A gRPC → Temporal → Gemini API → SQLite pipeline.

## Architecture

```
grpc_client  →  grpc_server  →  Temporal (GeminiEchoWorkflow)
                                     ├─ activity: call_gemini  → Gemini API
                                     └─ activity: save_to_db   → SQLite
```

## Setup order (one-time)

### 1. Compile proto stubs

```bash
python -m grpc_tools.protoc \
  -I proto \
  --python_out=proto/generated \
  --grpc_python_out=proto/generated \
  proto/gemini_echo.proto
```

### 2. Initialise the database

```bash
python storage/init_db.py
```

### 3. Add your Gemini API key

```bash
echo "GEMINI_API_KEY=your_key_here" > .env
```

## Running (3 terminals, all from project root)

### Terminal 1 — Temporal dev server

```bash
temporal server start-dev
```

### Terminal 2 — Temporal worker

```bash
python -m workflow.worker
```

### Terminal 3 — gRPC server

```bash
python -m server.grpc_server
```

## Sending a prompt

```bash
python -m client.grpc_client "What is the speed of light?"
```

# View Gemini usage here
https://aistudio.google.com/

# Braintrust
https://www.braintrust.dev/app/snitkdan-test/p/My%20Project?onboarding=true