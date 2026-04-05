# workflow

Temporal workflow, activities, and worker for `gemini_echo`.

## Files

| File            | Purpose                                                                        |
|-----------------|--------------------------------------------------------------------------------|
| `activities.py` | `open_db_connection`, `close_db_connection`, `call_gemini`, `save_to_db` activity definitions |
| `workflow.py`   | `GeminiEchoWorkflow` orchestration                                             |
| `worker.py`     | Worker process — polls `gemini-echo` task queue                                |

## Activities

| Activity              | Signature                                          | Description                                                    |
|-----------------------|----------------------------------------------------|----------------------------------------------------------------|
| `open_db_connection`  | `() → str`                                         | Opens a `DBClient`, registers it in a worker-local registry, and returns a connection id |
| `close_db_connection` | `(conn_id: str) → None`                            | Closes and deregisters the `DBClient` for the given connection id |
| `call_gemini`         | `(prompt: str) → str`                              | POSTs the prompt to the Gemini API and returns the text response |
| `save_to_db`          | `(conn_id: str, prompt: str, response: str) → int` | Persists the prompt and response via an existing connection, returns the new row id |

## Connection lifecycle

DB connections are managed explicitly per workflow run via a worker-local registry
(a module-level `dict` keyed by UUID). The workflow always calls `close_db_connection`
in a `try/finally` block, so the connection is released even if an intermediate
activity fails.

## Prerequisites

- A Temporal server must be running on `localhost:7233`.
  The easiest way during development:
  ```bash
  temporal server start-dev
  ```
- `GEMINI_API_KEY` must be set in the `.env` file at the project root.
- The SQLite DB must have been initialised:
  ```bash
  python storage/init_db.py
  ```

## Running the worker

Run from the **project root** so that the `storage` and `workflow` packages
are importable:

```bash
python -m workflow.worker
```