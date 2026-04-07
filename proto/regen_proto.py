#!/usr/bin/env python3

from __future__ import annotations

import argparse
import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

PROTO_DIR = REPO_ROOT / "proto"
OUT_DIR = PROTO_DIR / "generated"
PROTO_FILE = PROTO_DIR / "gemini_echo.proto"

FILES_TO_PATCH = [
    "gemini_echo_pb2_grpc.py",
    "gemini_echo_pb2_grpc.pyi",
]


def ensure_init_py(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    init_py = out_dir / "__init__.py"
    if not init_py.exists():
        init_py.write_text("", encoding="utf-8")


def run_protoc(out_dir: Path) -> None:
    rel_out_dir = out_dir.relative_to(REPO_ROOT)

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        "-I",
        str(PROTO_DIR.relative_to(REPO_ROOT)),
        f"--python_out={rel_out_dir}",
        f"--grpc_python_out={rel_out_dir}",
        f"--mypy_out={rel_out_dir}",
        f"--mypy_grpc_out={rel_out_dir}",
        str(PROTO_FILE.relative_to(REPO_ROOT)),
    ]

    print(f"Running protoc into {rel_out_dir}...")
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def patch_file(path: Path) -> None:
    if not path.exists():
        print(f"Skipping missing file: {path}")
        return

    original = path.read_text(encoding="utf-8")
    patched_lines: list[str] = []

    for line in original.splitlines(keepends=True):
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]

        if stripped.startswith("import gemini_echo_pb2"):
            patched_lines.append(f"{indent}from . {stripped}")
        else:
            patched_lines.append(line)

    patched = "".join(patched_lines)

    if patched != original:
        path.write_text(patched, encoding="utf-8")
        print(f"Patched: {path}")
    else:
        print(f"No changes needed: {path}")


def generate_into(out_dir: Path) -> None:
    ensure_init_py(out_dir)
    run_protoc(out_dir)

    print("Patching generated imports...")
    for filename in FILES_TO_PATCH:
        patch_file(out_dir / filename)


def directories_match(left: Path, right: Path) -> bool:
    if not left.exists() or not right.exists():
        return left.exists() == right.exists()

    cmp = filecmp.dircmp(left, right)

    if cmp.left_only:
        print(f"Only in {left}: {cmp.left_only}")
        return False

    if cmp.right_only:
        print(f"Only in {right}: {cmp.right_only}")
        return False

    if cmp.funny_files:
        print(f"Funny files while comparing {left} and {right}: {cmp.funny_files}")
        return False

    _, mismatch, errors = filecmp.cmpfiles(
        left,
        right,
        cmp.common_files,
        shallow=False,
    )

    if mismatch:
        print(f"Mismatched files in {left}: {mismatch}")
        return False

    if errors:
        print(f"Comparison errors in {left}: {errors}")
        return False

    for subdir in cmp.common_dirs:
        if not directories_match(left / subdir, right / subdir):
            return False

    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit nonzero if generated proto files differ from committed files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.check:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmpdir:
            tmp_out_dir = Path(tmpdir) / "generated"
            generate_into(tmp_out_dir)

            print("Comparing generated output with committed files...")
            if not directories_match(tmp_out_dir, OUT_DIR):
                print("Generated proto files are out of date.")
                sys.exit(1)
    else:
        generate_into(OUT_DIR)

    print("Done.")


if __name__ == "__main__":
    main()
