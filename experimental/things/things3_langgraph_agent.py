import json
import os
import re
import subprocess
import urllib.parse
from difflib import SequenceMatcher
from typing import Any, Literal, TypedDict, cast

import questionary
import things  # type: ignore[import-untyped]
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from rich.console import Console
from rich.markdown import Markdown

load_dotenv()

THINGS_AUTH_TOKEN: str = os.environ.get("THINGS_AUTH_TOKEN", "")
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")


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


class MatchCandidate(TypedDict):
    index: int
    uuid: str
    title: str
    score: float


class AgentState(TypedDict, total=False):
    todos: list[Todo]
    user_input: str
    intent: Literal["query", "complete", "clarify", "unknown"]
    parsed: dict[str, Any]
    response: str
    candidates: list[MatchCandidate]
    selected_todo: Todo | None
    pending_action: dict[str, Any] | None


Intent = Literal["query", "complete", "clarify", "unknown"]
RouteAfterClassify = Literal[
    "resolve_completion", "answer_query", "clarify", "unknown"
]
RouteAfterResolution = Literal["perform_completion", "end"]

CANNED_QUESTIONS: list[str] = [
    "What do I have to focus on?",
    "What do I have to focus on in <tag>? (pick a tag)",
]


def complete_todo(uuid: str) -> None:
    if not THINGS_AUTH_TOKEN:
        raise RuntimeError(
            "No Things auth token found. Set THINGS_AUTH_TOKEN in your .env "
            "file (Things → Settings → General)."
        )

    params: str = urllib.parse.urlencode(
        {
            "auth-token": THINGS_AUTH_TOKEN,
            "id": uuid,
            "completed": "true",
        }
    )
    url: str = f"things:///update?{params}"
    subprocess.run(["open", url], check=True)


def display_todos(todos: list[Todo]) -> None:
    print(f"\nToday's TODOs ({len(todos)} total)\n" + "-" * 60)

    for i, todo in enumerate(todos, start=1):
        title: str = todo.get("title", "(Untitled)")
        tags: list[str] = todo.get("tags", [])
        notes: str | None = todo.get("notes")
        area_title: str | None = todo.get("area_title")
        project_title: str | None = todo.get("project_title")

        print(f"{i:>2}. {title}")
        if tags:
            print(f"    Tags    : {', '.join(tags)}")
        if area_title:
            print(f"    Area    : {area_title}")
        if project_title:
            print(f"    Project : {project_title}")
        if notes:
            preview: str = notes[:100]
            suffix: str = "..." if len(notes) > 100 else ""
            print(f"    Notes   : {preview}{suffix}")
        print()


def normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def extract_indices(text: str, max_index: int) -> list[int]:
    matches: list[str] = re.findall(r"\b\d+\b", text)
    indices: list[int] = []

    for match in matches:
        idx: int = int(match)
        if 1 <= idx <= max_index and idx not in indices:
            indices.append(idx)

    return indices


def score_todo_match(query: str, todo: Todo) -> float:
    title: str = todo.get("title", "")
    if not title:
        return 0.0

    q: str = normalize_text(query)
    t: str = normalize_text(title)

    if not q or not t:
        return 0.0

    if q == t:
        return 1.0

    if q in t:
        return 0.92

    q_words: set[str] = set(q.split())
    t_words: set[str] = set(t.split())

    if q_words and q_words.issubset(t_words):
        return 0.88

    overlap: int = len(q_words & t_words)
    overlap_score: float = overlap / max(len(q_words), 1)

    sequence_score: float = SequenceMatcher(None, q, t).ratio()

    return max(overlap_score * 0.8, sequence_score * 0.75)


def find_matching_todos(
    query: str, todos: list[Todo]
) -> list[MatchCandidate]:
    candidates: list[MatchCandidate] = []

    for index, todo in enumerate(todos, start=1):
        uuid: str | None = todo.get("uuid")
        title: str = todo.get("title", "(Untitled)")
        if not uuid:
            continue

        score: float = score_todo_match(query, todo)
        if score >= 0.45:
            candidates.append(
                {
                    "index": index,
                    "uuid": uuid,
                    "title": title,
                    "score": round(score, 3),
                }
            )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates


def todos_for_llm(todos: list[Todo]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []

    for i, todo in enumerate(todos, start=1):
        serialized.append(
            {
                "index": i,
                "uuid": todo.get("uuid"),
                "title": todo.get("title"),
                "notes": todo.get("notes"),
                "tags": todo.get("tags", []),
                "area_title": todo.get("area_title"),
                "project_title": todo.get("project_title"),
                "status": todo.get("status"),
            }
        )

    return serialized


def get_llm() -> ChatGoogleGenerativeAI:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "No GEMINI_API_KEY found. Set GEMINI_API_KEY in your .env file."
        )

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.2,
        google_api_key=GEMINI_API_KEY,
    )


def load_todos_node(state: AgentState) -> AgentState:
    todos: list[Todo] = cast(list[Todo], things.today())
    return {
        **state,
        "todos": todos,
    }


def classify_intent_node(state: AgentState) -> AgentState:
    user_input: str = state["user_input"]
    todos: list[Todo] = state["todos"]

    system_prompt: str = """
You are an intent classifier for a Things TODO assistant.

Classify the user's request into one of:
- "complete": user wants to mark one or more TODOs complete
- "query": user wants analysis, filtering, grouping, summarization, or notes summary
- "clarify": user is answering a previous disambiguation prompt
- "unknown": unclear

Return strict JSON with this schema:
{
  "intent": "complete" | "query" | "clarify" | "unknown",
  "completion_query": string | null,
  "todo_indices": number[],
  "needs_notes_focus": boolean,
  "raw_filter": string | null
}

Rules:
- If the user says things like "complete groceries" or "mark buy groceries done",
  classify as "complete" and extract the title-like target into "completion_query".
- If the user references numbered TODOs like "1, 2, 3", include them in "todo_indices".
- If the user asks to summarize notes, set "needs_notes_focus" = true.
- If they are plainly replying to a disambiguation prompt with something like
  "1", "the second one", or a title among listed options, classify as "clarify".
- If uncertain, return "unknown".
"""

    human_prompt: str = f"""
Current TODO count: {len(todos)}

User input:
{user_input}
""".strip()

    llm: ChatGoogleGenerativeAI = get_llm()
    result = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
    )

    content: str | list[Any] = result.content
    text: str
    if isinstance(content, list):
        text = " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    else:
        text = str(content)

    parsed: dict[str, Any]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        lower: str = user_input.lower()
        intent: Intent = "unknown"
        if lower.startswith("complete ") or lower.startswith("mark "):
            intent = "complete"
        elif any(
            word in lower for word in ["summarize", "focus", "what do i have"]
        ):
            intent = "query"

        parsed = {
            "intent": intent,
            "completion_query": None,
            "todo_indices": extract_indices(user_input, len(todos)),
            "needs_notes_focus": "notes" in lower,
            "raw_filter": None,
        }

    return {
        **state,
        "intent": cast(Intent, parsed.get("intent", "unknown")),
        "parsed": parsed,
    }


def resolve_completion_node(state: AgentState) -> AgentState:
    todos: list[Todo] = state["todos"]
    user_input: str = state["user_input"]
    parsed: dict[str, Any] = state.get("parsed", {})
    completion_query: Any = parsed.get("completion_query")

    if not isinstance(completion_query, str) or not completion_query.strip():
        lower: str = user_input.lower()
        completion_query = re.sub(
            r"^(complete|mark|finish)\s+", "", lower
        ).strip()
        completion_query = re.sub(
            r"\s+(done|complete|completed)$", "", completion_query
        )

    completion_query = str(completion_query).strip()

    if not completion_query:
        return {
            **state,
            "response": "I couldn't tell which TODO you want to complete.",
            "candidates": [],
        }

    indices: list[int] = parsed.get("todo_indices", [])
    if len(indices) == 1:
        idx: int = indices[0]
        if 1 <= idx <= len(todos):
            selected: Todo = todos[idx - 1]
            return {
                **state,
                "selected_todo": selected,
                "candidates": [],
            }

    candidates: list[MatchCandidate] = find_matching_todos(
        completion_query, todos
    )

    if not candidates:
        return {
            **state,
            "response": f"I couldn't find a TODO matching '{completion_query}'.",
            "candidates": [],
        }

    if len(candidates) == 1 or (
        len(candidates) >= 2
        and candidates[0]["score"] >= 0.9
        and candidates[0]["score"] - candidates[1]["score"] >= 0.08
    ):
        top: MatchCandidate = candidates[0]
        selected = todos[top["index"] - 1]
        return {
            **state,
            "selected_todo": selected,
            "candidates": candidates,
        }

    top_candidates: list[MatchCandidate] = candidates[:5]
    lines: list[str] = [
        f"I found multiple possible matches for '{completion_query}'. "
        "Which one did you mean?"
    ]
    for item in top_candidates:
        lines.append(f"{item['index']}. {item['title']}")

    lines.append("Reply with the number or exact title.")

    return {
        **state,
        "response": "\n".join(lines),
        "candidates": top_candidates,
        "pending_action": {
            "type": "complete_disambiguation",
            "query": completion_query,
        },
    }


def answer_query_node(state: AgentState) -> AgentState:
    todos: list[Todo] = state["todos"]
    user_input: str = state["user_input"]
    parsed: dict[str, Any] = state.get("parsed", {})

    indexed: list[dict[str, Any]] = todos_for_llm(todos)
    todo_indices: list[int] = parsed.get("todo_indices", [])
    needs_notes_focus: bool = bool(parsed.get("needs_notes_focus", False))

    selected_subset: list[dict[str, Any]]
    if todo_indices:
        index_set: set[int] = set(todo_indices)
        selected_subset = [
            item for item in indexed if item["index"] in index_set
        ]
    else:
        selected_subset = indexed

    system_prompt: str = """
You are a productivity assistant working over a Things TODO list.

Your job:
- Answer the user's question using only the provided TODO data.
- When summarizing, group by tags and similar titles where relevant.
- Do not include a top-level executive summary.
- Do not mention deadlines unless explicitly asked.
- Be concise, structured, and useful.
- If the user asks what to focus on excluding a project/area/title like
  "not in Evening Routine", filter those items out if the data supports it.
- If the user asks to summarize notes for numbered TODOs, focus only on the
  notes from those TODOs.
- If notes are empty, say so clearly.
"""

    human_payload: dict[str, Any] = {
        "user_request": user_input,
        "notes_focus": needs_notes_focus,
        "todos": selected_subset,
    }

    llm: ChatGoogleGenerativeAI = get_llm()
    result = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=json.dumps(human_payload, indent=2)),
        ]
    )

    content: str | list[Any] = result.content
    text: str
    if isinstance(content, list):
        text = " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    else:
        text = str(content)

    return {
        **state,
        "response": text.strip(),
    }


def clarify_node(state: AgentState) -> AgentState:
    todos: list[Todo] = state["todos"]
    user_input: str = state["user_input"]
    candidates: list[MatchCandidate] = state.get("candidates", [])

    if not candidates:
        return {
            **state,
            "response": "I need more context to resolve that.",
        }

    indices: list[int] = extract_indices(user_input, len(todos))
    if len(indices) == 1:
        idx: int = indices[0]
        matching: list[MatchCandidate] = [
            c for c in candidates if c["index"] == idx
        ]
        if matching:
            selected: Todo = todos[idx - 1]
            return {
                **state,
                "selected_todo": selected,
                "response": "",
            }

    normalized_input: str = normalize_text(user_input)
    for candidate in candidates:
        if normalize_text(candidate["title"]) == normalized_input:
            selected = todos[candidate["index"] - 1]
            return {
                **state,
                "selected_todo": selected,
                "response": "",
            }

    fuzzy: list[MatchCandidate] = find_matching_todos(user_input, todos)
    if fuzzy:
        top: MatchCandidate = fuzzy[0]
        if any(top["index"] == c["index"] for c in candidates):
            selected = todos[top["index"] - 1]
            return {
                **state,
                "selected_todo": selected,
                "response": "",
            }

    return {
        **state,
        "response": "I still couldn't tell which one you meant. "
        "Please reply with the number shown in the list.",
    }


def perform_completion_node(state: AgentState) -> AgentState:
    selected: Todo | None = state.get("selected_todo")
    if not selected:
        return {
            **state,
            "response": state.get("response", "No TODO selected."),
        }

    uuid: str | None = selected.get("uuid")
    title: str = selected.get("title", "(Untitled)")

    if not uuid:
        return {
            **state,
            "response": f"Error: '{title}' has no UUID.",
        }

    complete_todo(uuid)

    return {
        **state,
        "response": f"✓ Marked as complete: {title}",
        "pending_action": None,
        "candidates": [],
        "selected_todo": None,
    }


def route_after_classify(state: AgentState) -> RouteAfterClassify:
    intent: Intent = state.get("intent", "unknown")
    if intent == "complete":
        return "resolve_completion"
    if intent == "query":
        return "answer_query"
    if intent == "clarify":
        return "clarify"
    return "unknown"


def route_after_resolution(state: AgentState) -> RouteAfterResolution:
    if state.get("selected_todo") is not None:
        return "perform_completion"
    return "end"


def build_graph() -> CompiledStateGraph[AgentState]:
    graph: StateGraph[AgentState] = StateGraph(AgentState)

    graph.add_node("load_todos", load_todos_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("resolve_completion", resolve_completion_node)
    graph.add_node("answer_query", answer_query_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("perform_completion", perform_completion_node)

    graph.set_entry_point("load_todos")
    graph.add_edge("load_todos", "classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "resolve_completion": "resolve_completion",
            "answer_query": "answer_query",
            "clarify": "clarify",
            "unknown": END,
        },
    )

    graph.add_conditional_edges(
        "resolve_completion",
        route_after_resolution,
        {
            "perform_completion": "perform_completion",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "clarify",
        route_after_resolution,
        {
            "perform_completion": "perform_completion",
            "end": END,
        },
    )

    graph.add_edge("answer_query", END)
    graph.add_edge("perform_completion", END)

    return graph.compile()


def pick_tag(todos: list[Todo]) -> str | None:
    tags: list[str] = sorted(
        {tag for todo in todos for tag in todo.get("tags", [])}
    )
    if not tags:
        print("No tags found in today's TODOs.")
        return None

    tag: str | None = questionary.select(
        "Choose a tag:",
        choices=tags,
    ).ask()
    return tag


def show_canned_menu(todos: list[Todo]) -> str | None:
    choice: str | None = questionary.select(
        "Choose a question:",
        choices=CANNED_QUESTIONS,
    ).ask()

    if choice is None:
        return None

    if choice == CANNED_QUESTIONS[0]:
        return "What do I have to focus on?"

    if choice == CANNED_QUESTIONS[1]:
        tag: str | None = pick_tag(todos)
        if tag is None:
            return None
        return (
            f"What do I have to focus on in the '{tag}' tag? "
            "Analyze the notes and see what's similar between them "
            "in terms of title and content."
        )

    return None


def main() -> None:
    app: CompiledStateGraph[AgentState] = build_graph()
    console = Console()

    console.print("Things Assistant", style="bold")
    console.print("Press Enter or type 'menu' to pick a canned question.")
    console.print("Type 'help' for examples, or 'quit' to exit.")

    carry_state: AgentState = {
        "candidates": [],
        "pending_action": None,
    }

    try:
        while True:
            print()
            try:
                user_input: str = input("> ").strip()
            except KeyboardInterrupt:
                print()
                print("Goodbye.")
                break

            lower: str = user_input.lower()

            if not user_input or lower == "menu":
                current_todos_for_menu: list[Todo] = cast(
                    list[Todo], things.today()
                )
                canned: str | None = show_canned_menu(current_todos_for_menu)
                if canned:
                    print(f"> {canned}")
                    user_input = canned
                    lower = user_input.lower()
                else:
                    continue

            if lower in {"quit", "exit"}:
                print("Goodbye.")
                break

            if lower == "help":
                console.print(
                    Markdown(
                        "**Examples:**\n"
                        "- What do I have to focus on that's not in Evening Routine?\n"
                        "- Summarize the Notes section of TODOs 1, 2, 3\n"
                        "- Complete Buy groceries\n"
                        "- Complete groceries\n"
                        "- Complete 2\n"
                        "- Show todos\n"
                    )
                )
                continue

            if lower == "show todos":
                todos: list[Todo] = cast(list[Todo], things.today())
                if not todos:
                    print("No TODOs for today!")
                else:
                    display_todos(todos)
                continue

            pending_action: dict[str, Any] | None = carry_state.get(
                "pending_action"
            )
            state_input: AgentState
            if (
                pending_action is not None
                and pending_action.get("type") == "complete_disambiguation"
            ):
                current_todos: list[Todo] = cast(list[Todo], things.today())
                state_input = {
                    "todos": current_todos,
                    "user_input": user_input,
                    "intent": "clarify",
                    "candidates": carry_state.get("candidates", []),
                    "pending_action": pending_action,
                }
            else:
                state_input = {
                    "user_input": user_input,
                    "candidates": [],
                    "pending_action": None,
                }

            try:
                result: AgentState = cast(AgentState, app.invoke(state_input))
            except Exception as exc:
                console.print(f"Error: {exc}", style="red")
                continue

            response: str | None = result.get("response")
            if response:
                console.print()
                console.rule(style="dim")
                console.print(Markdown(response))
                console.rule(style="dim")
                console.print()
            else:
                print("Done.")

            carry_state = {
                "candidates": result.get("candidates", []),
                "pending_action": result.get("pending_action"),
            }
    except KeyboardInterrupt:
        print()
        print("Goodbye.")

if __name__ == "__main__":
    main()