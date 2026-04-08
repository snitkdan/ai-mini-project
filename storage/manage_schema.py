#!/usr/bin/env python3
"""Interactive CLI to add or remove a column from the transactions schema.

After running, drop and re-create the database:
    python -m storage.init_db
"""

import re
import sys
from pathlib import Path

from logger import logger


STORAGE_DIR = Path(__file__).parent
SCHEMA_PATH = STORAGE_DIR / "schema.py"
CLIENT_PATH = STORAGE_DIR / "client.py"

SQL_TYPES = ["TEXT", "INTEGER", "REAL", "BLOB", "BOOLEAN"]
SQL_TO_PY: dict[str, str] = {
    "TEXT": "str",
    "INTEGER": "int",
    "REAL": "float",
    "BLOB": "bytes",
    "BOOLEAN": "bool",
}


# ── Prompt helpers ────────────────────────────────────────────────────────────


def prompt_menu(heading: str, options: list[str]) -> str:
    logger.info("\n%s", heading)
    for i, opt in enumerate(options, 1):
        logger.info("  %d. %s", i, opt)
    while True:
        raw = input("Choice: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        logger.warning("Enter a number from 1 to %d.", len(options))


def prompt_yes_no(question: str) -> bool:
    while True:
        raw = input(f"{question} [y/n]: ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        logger.warning("Enter y or n.")


# ── Source helpers ────────────────────────────────────────────────────────────


def ensure_optional_import(source: str) -> str:
    """Add 'from typing import Optional' after the last import if absent."""
    if "Optional" in source:
        return source
    lines = source.splitlines(keepends=True)
    last_import_idx = -1
    for i, line in enumerate(lines):
        if re.match(r"^(?:from|import)\s+", line):
            last_import_idx = i
    if last_import_idx >= 0:
        lines.insert(last_import_idx + 1, "from typing import Optional\n")
    return "".join(lines)


def get_sql_columns(schema_source: str) -> list[str]:
    m = re.search(
        r'CREATE_TABLE_SQL\s*:\s*str\s*=\s*[furbFURB]*"""(.*?)"""',
        schema_source,
        re.DOTALL,
    )
    if not m:
        msg = "CREATE_TABLE_SQL not found in schema.py"
        raise ValueError(msg)
    cols = []
    for line in m.group(1).splitlines():
        stripped = line.strip().rstrip(",")
        if not stripped or stripped.upper().startswith("CREATE") or stripped == ")":
            continue
        col_m = re.match(r"^(\w+)\s+", stripped)
        if col_m:
            cols.append(col_m.group(1))
    return cols


# ── schema.py mutations ───────────────────────────────────────────────────────


def schema_add_column(
    source: str, col_name: str, sql_type: str, *, required: bool
) -> str:
    constraint = "NOT NULL" if required else "NULL"
    new_line = f"        {col_name:<9} {sql_type:<7} {constraint}"

    m = re.search(
        r'(CREATE_TABLE_SQL\s*:\s*str\s*=\s*[furbFURB]*""")(.*?)(""")',
        source,
        re.DOTALL,
    )
    if not m:
        msg = "CREATE_TABLE_SQL not found"
        raise ValueError(msg)

    lines = m.group(2).rstrip().splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() and lines[i].strip() != ")":
            lines[i] = lines[i].rstrip().rstrip(",") + ","
            lines.insert(i + 1, new_line)
            break

    new_body = "\n".join(lines) + "\n"
    return source[: m.start()] + m.group(1) + new_body + m.group(3) + source[m.end() :]


def schema_remove_column(source: str, col_name: str) -> str:
    m = re.search(
        r'(CREATE_TABLE_SQL\s*:\s*str\s*=\s*[furbFURB]*""")(.*?)(""")',
        source,
        re.DOTALL,
    )
    if not m:
        msg = "CREATE_TABLE_SQL not found"
        raise ValueError(msg)

    lines = [
        line
        for line in m.group(2).splitlines(keepends=True)
        if not re.match(rf"^\s+{col_name}\s+", line)
    ]
    # Strip trailing comma from new last column line
    result = "".join(lines).rstrip().splitlines()
    for i in range(len(result) - 1, -1, -1):
        if result[i].strip() and result[i].strip() != ")":
            result[i] = result[i].rstrip().rstrip(",")
            break
    new_body = "\n".join(result) + "\n"
    return source[: m.start()] + m.group(1) + new_body + m.group(3) + source[m.end() :]


def dataclass_add_field(
    source: str, col_name: str, py_type: str, *, required: bool
) -> str:
    new_field = (
        f"    {col_name}: {py_type}"
        if required
        else f"    {col_name}: Optional[{py_type}] = None"
    )
    m = re.search(r"(class Transaction:.*?)(\n\n|\Z)", source, re.DOTALL)
    if not m:
        msg = "Transaction dataclass not found"
        raise ValueError(msg)
    new_class = m.group(1).rstrip() + "\n" + new_field
    return source[: m.start()] + new_class + source[m.start() + len(m.group(1)) :]


def dataclass_remove_field(source: str, col_name: str) -> str:
    lines = source.splitlines(keepends=True)
    return "".join(line for line in lines if not re.match(rf"^\s+{col_name}\s*:", line))


# ── client.py mutations ───────────────────────────────────────────────────────


def insert_add_param(
    source: str, col_name: str, py_type: str, *, required: bool
) -> str:
    new_param = (
        f", {col_name}: {py_type}"
        if required
        else f", {col_name}: Optional[{py_type}] = None"
    )
    return re.sub(
        r"(def insert\(self(?:[^)]*?))\)\s*->\s*int\s*:",
        rf"\1{new_param}) -> int:",
        source,
        count=1,
        flags=re.DOTALL,
    )


def insert_remove_param(source: str, col_name: str) -> str:
    return re.sub(
        rf",\s*{col_name}\s*:[^,)]*",
        "",
        source,
        count=1,
    )


def _find_insert_def(lines: list[str]) -> int:
    idx = next(
        (i for i, line in enumerate(lines) if re.match(r"\s+def insert\(", line)),
        None,
    )
    if idx is None:
        msg = "insert method not found in client.py"
        raise ValueError(msg)
    return idx


def _find_body_start(lines: list[str], def_idx: int) -> int:
    for i in range(def_idx, len(lines)):
        if lines[i].rstrip().endswith(":"):
            return i + 1
    return def_idx + 1


def _skip_docstring(lines: list[str], body_start: int) -> int:
    first = lines[body_start].strip()
    if not first.startswith('"""'):
        return body_start
    if first.count('"""') >= 2 and len(first) > 6:
        return body_start + 1
    for i in range(body_start + 1, len(lines)):
        if '"""' in lines[i]:
            return i + 1
    return body_start


def insert_add_todo(source: str) -> str:
    """Prepend raise RuntimeError('TODO: implement this') to insert body."""
    lines = source.splitlines(keepends=True)

    def_idx = _find_insert_def(lines)
    body_start = _find_body_start(lines, def_idx)
    insert_at = _skip_docstring(lines, body_start)

    if any(
        "TODO: implement this" in line for line in lines[body_start : body_start + 6]
    ):
        return source

    lines.insert(insert_at, '        raise RuntimeError("TODO: implement this")\n')
    return "".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    action = prompt_menu(
        "What would you like to do?", ["Add a column", "Remove a column"]
    )

    schema_source = SCHEMA_PATH.read_text()
    client_source = CLIENT_PATH.read_text()

    if action == "Add a column":
        col_name = input("\nColumn name: ").strip()
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col_name):
            logger.error("Invalid column name.")
            sys.exit(1)

        sql_type = prompt_menu("SQL type:", SQL_TYPES)
        py_type = SQL_TO_PY[sql_type]
        required = prompt_yes_no("Required (NOT NULL)?")

        logger.info(
            "\nAdding '%s' (%s / %s, %s)...",
            col_name,
            sql_type,
            py_type,
            "NOT NULL" if required else "NULL",
        )

        schema_source = schema_add_column(
            schema_source, col_name, sql_type, required=required
        )
        schema_source = dataclass_add_field(
            schema_source, col_name, py_type, required=required
        )
        if not required:
            schema_source = ensure_optional_import(schema_source)
            client_source = ensure_optional_import(client_source)

        client_source = insert_add_param(
            client_source, col_name, py_type, required=required
        )
        client_source = insert_add_todo(client_source)

    else:
        columns = [col for col in get_sql_columns(schema_source) if col != "id"]
        if not columns:
            logger.error("No removable columns found.")
            sys.exit(1)

        col_name = prompt_menu("Which column to remove?", columns)
        logger.info("\nRemoving '%s'...", col_name)

        schema_source = schema_remove_column(schema_source, col_name)
        schema_source = dataclass_remove_field(schema_source, col_name)
        client_source = insert_remove_param(client_source, col_name)
        client_source = insert_add_todo(client_source)

    SCHEMA_PATH.write_text(schema_source)
    CLIENT_PATH.write_text(client_source)

    logger.info("\nDone! Updated:")
    logger.info("  %s", SCHEMA_PATH)
    logger.info("  %s", CLIENT_PATH)
    logger.info("\nNext steps:")
    logger.info("  1. Implement the new insert logic in client.py (find the TODO).")
    logger.info("  2. Drop and re-create the database: python -m storage.init_db")


if __name__ == "__main__":
    main()
