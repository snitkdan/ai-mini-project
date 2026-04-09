import os
import subprocess
import urllib.parse
from typing import TypedDict, cast

import things  # type: ignore[import-untyped]
from dotenv import load_dotenv

load_dotenv()

THINGS_AUTH_TOKEN = os.environ.get("THINGS_AUTH_TOKEN", "")


class Checklist(TypedDict, total=False):
    uuid: str
    title: str
    status: str


class Todo(TypedDict, total=False):
    uuid: str
    title: str
    notes: str | None
    status: str
    area: str | None
    area_title: str | None
    project: str | None
    project_title: str | None
    tags: list[str]
    deadline: str | None
    start_date: str | None
    stop_date: str | None
    checklist: list[Checklist]
    contact: str | None
    type: str
    trashed: bool
    last_modified: str
    created: str


def display_todos(todos: list[Todo]) -> None:
    print(f"Today's TODOs ({len(todos)} total)\n" + "-" * 40)

    for i, todo in enumerate(todos, start=1):
        title: str = todo.get("title", "(Untitled)")
        notes: str | None = todo.get("notes")
        tags: list[str] = todo.get("tags", [])

        print(f"{i:>2}. {title}")
        if tags:
            print(f"      Tags  : {', '.join(tags)}")
        if notes:
            print(f"      Notes : {notes[:80]}{'...' if len(notes) > 80 else ''}")
        print()


def complete_todo(uuid: str) -> None:
    if not THINGS_AUTH_TOKEN:
        raise RuntimeError(
            "No Things auth token found. Set THINGS_AUTH_TOKEN in your .env "
            "file (Things → Settings → General)."
        )

    params = urllib.parse.urlencode({
        "auth-token": THINGS_AUTH_TOKEN,
        "id": uuid,
        "completed": "true",
    })
    url = f"things:///update?{params}"
    subprocess.run(["open", url], check=True)


def prompt_selection(todos: list[Todo]) -> Todo | None:
    raw = input("Enter the number of a TODO to complete (or press Enter to quit): ").strip()
    if not raw:
        return None

    try:
        index = int(raw) - 1
    except ValueError:
        print("Invalid input — please enter a number.")
        return None

    if not (0 <= index < len(todos)):
        print(f"Out of range — pick a number between 1 and {len(todos)}.")
        return None

    return todos[index]


def main() -> None:
    todos: list[Todo] = cast(list[Todo], things.today())

    if not todos:
        print("No TODOs for today!")
        return

    display_todos(todos)

    selected = prompt_selection(todos)
    if selected is None:
        print("No selection made — exiting.")
        return

    uuid = selected.get("uuid")
    title = selected.get("title", "(Untitled)")

    if not uuid:
        print(f"Error: '{title}' has no UUID.")
        return

    complete_todo(uuid)
    print(f"✓ Marked as complete: {title}")


if __name__ == "__main__":
    main()