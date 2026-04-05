# storage

SQLite persistence layer for `gemini_echo`.

## Files

| File         | Purpose                                      |
|--------------|----------------------------------------------|
| `init_db.py` | One-off script to create the DB and schema   |
| `client.py`  | `DBClient` — insert / query / list rows      |

## Usage

### Initialise the database (run once)

```bash
python storage/init_db.py
```

This creates `gemini_echo.db` at the project root.

### Using `DBClient` in code

```python
from storage.client import DBClient, Transaction

db = DBClient()

# Insert
row_id = db.insert(prompt="Hello", response="Hi there!")

# Query by id
txn: Transaction | None = db.query_by_id(row_id)

# List all
all_txns: list[Transaction] = db.list_all()

# Most recent
latest: Transaction | None = db.latest()
```