from __future__ import annotations

import argparse

from simulate_evacuations import run_experiment_set


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--n-iter", type=int, default=200)
    p.add_argument("--plots", action="store_true")
    p.add_argument("--stem", type=str, default="evac_v0_default")
    args = p.parse_args()

    run_experiment_set(
        separation_rows_levels=[0, 5, 10, 20],
        pct_separated_levels=[0.0, 0.10, 0.30],
        reunion_behavior_levels=["WAIT", "SEEK"],
        n_iter=int(args.n_iter),
        seed=int(args.seed),
        write_plots=bool(args.plots),
        stem=str(args.stem),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
