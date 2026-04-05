# workflow

Temporal workflow, activities, and worker for `gemini_echo`.

## Files

| File            | Purpose                                             |
|-----------------|-----------------------------------------------------|
| `activities.py` | `call_gemini` and `save_to_db` activity definitions |
| `workflow.py`   | `GeminiEchoWorkflow` orchestration                  |
| `worker.py`     | Worker process — polls `gemini-echo` task queue     |

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