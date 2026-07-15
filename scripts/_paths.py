from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    scripts: Path
    data: Path
    tables: Path
    figures: Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_paths() -> ProjectPaths:
    root = get_project_root()
    return ProjectPaths(
        root=root,
        scripts=root / "scripts",
        data=root / "data",
        tables=root / "tables",
        figures=root / "figures",
    )

