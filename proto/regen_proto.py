#!/usr/bin/env python3

from pathlib import Path
import argparse
import subprocess
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

PROTO_DIR = REPO_ROOT / "proto"
OUT_DIR = PROTO_DIR / "generated"

PROTO_FILE = PROTO_DIR / "gemini_echo.proto"

FILES_TO_PATCH = [
    OUT_DIR / "gemini_echo_pb2_grpc.py",
    OUT_DIR / "gemini_echo_pb2_grpc.pyi",
]


def ensure_init_py() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    init_py = OUT_DIR / "__init__.py"
    if not init_py.exists():
        init_py.write_text("", encoding="utf-8")
        print(f"Created: {init_py}")


def run_protoc() -> None:
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        "-I",
        "proto",
        "--python_out=proto/generated",
        "--grpc_python_out=proto/generated",
        "--mypy_out=proto/generated",
        "--mypy_grpc_out=proto/generated",
        "proto/gemini_echo.proto",
    ]

    print("Running protoc...")
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def patch_file(path: Path) -> None:
    if not path.exists():
        print(f"Skipping missing file: {path}")
        return

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    patched_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        indent = line[: len(line) - len(line.lstrip())]
        newline = "\n" if line.endswith("\n") else ""

        if stripped.startswith("import gemini_echo_pb2"):
            remainder = stripped[len("import gemini_echo_pb2") :]
            patched_lines.append(
                f"{indent}from . import gemini_echo_pb2{remainder}{newline}"
            )
        else:
            patched_lines.append(line)

    patched = "".join(patched_lines)

    if patched != original:
        path.write_text(patched, encoding="utf-8")
        print(f"Patched: {path}")
    else:
        print(f"No changes needed: {path}")


def check_for_changes() -> int:
    cmd = ["git", "diff", "--exit-code", "--", "proto/generated"]
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit nonzero if regenerating proto files changes committed files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ensure_init_py()
    run_protoc()

    print("Patching generated imports...")
    for path in FILES_TO_PATCH:
        patch_file(path)

    if args.check:
        print("Checking for generated file changes...")
        rc = check_for_changes()
        if rc != 0:
            print("Generated proto files are out of date.")
            sys.exit(rc)

    print("Done.")


if __name__ == "__main__":
    main()
