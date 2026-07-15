#!/usr/bin/env python3
"""Block git publish if any path escapes the simulation repo root.

Run manually before push:
    python scripts/verify_publish_scope.py

Pre-commit (staged files only):
    python scripts/verify_publish_scope.py --staged
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

# Path segments that must never appear in published repository paths.
FORBIDDEN_SEGMENTS: frozenset[str] = frozenset(
    {
        ".env",
        ".venv",
        "venv",
        "20_mails",
        "03_reviews",
        "90_finance",
        "91_family",
        "10_knowledge_base",
        "00_career_management",
        "04_papers",
        "06_projects",
        "07_internships",
        "08_learning",
        "09_implementations",
        "30_media",
        "40_literature",
        "50_law",
        "70_publishing houses",
        "71_universities",
        "personal_cloud",
    }
)

# Substrings that indicate a path was added from outside the repo root.
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "../",
    "..\\",
    "/personal_cloud/",
    "\\personal_cloud\\",
    "personal_cloud/",
    "personal_cloud\\",
)


def find_git_executable() -> str:
    override = os.environ.get("GIT_EXECUTABLE")
    if override:
        return override
    found = shutil.which("git")
    if found:
        return found
    for candidate in (
        Path(r"C:\Program Files\Git\bin\git.exe"),
        Path(r"C:\Program Files (x86)\Git\bin\git.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    return "git"


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    git_exe = find_git_executable()
    return subprocess.run(
        [git_exe, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def get_git_cwd() -> Path:
    return Path(__file__).resolve().parents[1]


def get_repo_root() -> Path:
    return get_git_cwd()


def check_git_toplevel(repo_root: Path) -> str | None:
    result = run_git(["rev-parse", "--show-toplevel"], repo_root)
    if result.returncode != 0:
        return "Could not determine git top-level directory (is this a git repo?)."
    toplevel_name = Path(result.stdout.strip()).name
    if toplevel_name != "aircraft_passenger_simulation":
        return (
            f"Git repo must live in aircraft_passenger_simulation/ "
            f"(found {toplevel_name!r}). Do not init git at personal_cloud/ root."
        )
    return None


def normalize_repo_path(raw: str) -> str:
    return raw.strip().replace("\\", "/")


def collect_paths(repo_root: Path, staged_only: bool) -> list[str]:
    if staged_only:
        result = run_git(
            ["diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            repo_root,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git diff --cached failed")
        return [line for line in result.stdout.splitlines() if line.strip()]

    result = run_git(["ls-files"], repo_root)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def is_absolute_path(path: str) -> bool:
    if path.startswith("/") or path.startswith("\\\\"):
        return True
    if len(path) >= 3 and path[1] == ":" and path[2] in ("/", "\\"):
        return True
    return False


def validate_path(repo_root: Path, raw_path: str) -> list[str]:
    errors: list[str] = []
    path = normalize_repo_path(raw_path)
    if not path:
        return errors

    if is_absolute_path(path):
        errors.append(f"absolute path not allowed: {path}")
        return errors

    pure = PurePosixPath(path)
    if pure.is_absolute():
        errors.append(f"absolute path not allowed: {path}")
        return errors

    parts = pure.parts
    if ".." in parts:
        errors.append(f"path escapes repo root via ..: {path}")

    for segment in parts:
        if segment in FORBIDDEN_SEGMENTS:
            errors.append(f"forbidden segment {segment!r} in {path}")

    lowered = path.lower()
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle.lower() in lowered:
            errors.append(f"forbidden substring {needle!r} in {path}")

    resolved = (repo_root / path).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        errors.append(f"path resolves outside repo root: {path} -> {resolved}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify tracked/staged git paths stay inside the simulation repo."
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check only staged files (pre-commit). Default: all tracked files.",
    )
    args = parser.parse_args()

    repo_root = get_repo_root()
    scope_label = "staged" if args.staged else "tracked"

    toplevel_error = check_git_toplevel(repo_root)
    if toplevel_error:
        print(f"PUBLISH SCOPE VIOLATION: {toplevel_error}", file=sys.stderr)
        return 1

    try:
        paths = collect_paths(repo_root, staged_only=args.staged)
    except RuntimeError as exc:
        print(f"PUBLISH SCOPE CHECK FAILED: {exc}", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for path in paths:
        all_errors.extend(validate_path(repo_root, path))

    if all_errors:
        print(
            f"PUBLISH SCOPE VIOLATION ({len(all_errors)} issue(s), {scope_label} files):",
            file=sys.stderr,
        )
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nThis repository may publish ONLY contents of aircraft_passenger_simulation/.",
            file=sys.stderr,
        )
        print(
            "See GITHUB_PUBLISH.md. Do not run git/gh from personal_cloud/ root.",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: {len(paths)} {scope_label} path(s) within "
        f"{repo_root.name}/ publish boundary."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
