"""Sensitivity of reunion_probability at key scenario (30% separated, 10 rows, WAIT)."""

from __future__ import annotations

import argparse

import pandas as pd

from _paths import get_paths
from simulate_evacuations import Scenario, run_monte_carlo, summarize_runs


def run_reunion_prob_sensitivity(
    prob_levels: list[float],
    separation_rows: int,
    pct_separated: float,
    reunion_behavior: str,
    n_iter: int,
    seed: int,
) -> pd.DataFrame:
    runs_all: list[pd.DataFrame] = []
    for prob in prob_levels:
        sc = Scenario(
            separation_rows=int(separation_rows),
            pct_separated=float(pct_separated),
            reunion_behavior=reunion_behavior,  # type: ignore[arg-type]
            seed=int(seed),
            n_iter=int(n_iter),
            reunion_probability=float(prob),
        )
        runs_all.append(run_monte_carlo(sc))
    runs = pd.concat(runs_all, ignore_index=True)
    return summarize_runs(runs)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--n-iter", type=int, default=200)
    p.add_argument(
        "--probs",
        type=float,
        nargs="+",
        default=[0.5, 0.8, 1.0],
    )
    p.add_argument("--separation-rows", type=int, default=10)
    p.add_argument("--pct-separated", type=float, default=0.30)
    p.add_argument("--reunion", type=str, default="WAIT", choices=["WAIT", "SEEK"])
    args = p.parse_args()

    df = run_reunion_prob_sensitivity(
        prob_levels=[float(x) for x in args.probs],
        separation_rows=int(args.separation_rows),
        pct_separated=float(args.pct_separated),
        reunion_behavior=str(args.reunion),
        n_iter=int(args.n_iter),
        seed=int(args.seed),
    )
    paths = get_paths()
    paths.tables.mkdir(parents=True, exist_ok=True)
    out = paths.tables / "sensitivity_reunion_prob.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
