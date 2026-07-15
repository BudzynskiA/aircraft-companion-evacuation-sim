"""Run timeout and reunion_probability sensitivity analyses."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run_script(name: str, extra: list[str]) -> None:
    script = Path(__file__).resolve().parent / name
    cmd = [sys.executable, str(script), *extra]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Run all sensitivity analyses for v0 headline scenarios.")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--n-iter", type=int, default=200)
    p.add_argument(
        "--timeouts",
        type=int,
        nargs="+",
        default=[20, 80, 200],
        help="reunion_timeout_ticks values (default 20, 80, 200)",
    )
    p.add_argument(
        "--probs",
        type=float,
        nargs="+",
        default=[0.5, 0.8, 1.0],
        help="reunion_probability levels (default 0.5, 0.8, 1.0)",
    )
    args = p.parse_args()

    common = ["--seed", str(args.seed), "--n-iter", str(args.n_iter)]

    _run_script(
        "sensitivity_timeout.py",
        common + ["--timeouts", *[str(t) for t in args.timeouts]],
    )
    _run_script(
        "sensitivity_reunion_prob.py",
        common + ["--probs", *[str(x) for x in args.probs]],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
