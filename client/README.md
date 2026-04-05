# client

gRPC client for `gemini_echo`. Sends a prompt to the server and prints
the Gemini response along with the latest database record.

## Prerequisites

- Proto stubs compiled into `proto/generated/`.
- `storage/init_db.py` run at least once.
- `workflow/worker.py` running.
- `server/grpc_server.py` running.

## Usage

Run from the **project root**:

```bash
python -m client.grpc_client "Explain black holes in one sentence."
```

### Example output

```
============================================================
LATEST DATABASE RECORD
============================================================
  ID        : 7
  Timestamp : 2026-04-05T17:00:00.000Z
  Prompt    : Explain black holes in one sentence.
  Response  : A black hole is a region of spacetime where gravity is so strong…
============================================================
```