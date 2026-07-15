"""Sensitivity of reunion_timeout_ticks on headline scenarios (30% separated)."""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from _paths import get_paths
from simulate_evacuations import AgentConfig, CabinConfig, ExitConfig, simulate_once


def run_timeout_sensitivity(
    timeout_levels: list[int],
    separation_rows_levels: list[int],
    pct_separated: float,
    reunion_behaviors: list[str],
    n_iter: int,
    seed: int,
) -> pd.DataFrame:
    cabin = CabinConfig()
    exits = ExitConfig()
    rows: list[dict] = []

    for timeout in timeout_levels:
        agents = AgentConfig(reunion_timeout_ticks=int(timeout))
        for rb in reunion_behaviors:
            for d in separation_rows_levels:
                vals: list[float] = []
                cf: list[float] = []
                succ: list[float] = []
                for k in range(n_iter):
                    rng = np.random.default_rng(seed + k)
                    m = simulate_once(
                        cabin,
                        exits,
                        agents,
                        int(d),
                        pct_separated,
                        rb,  # type: ignore[arg-type]
                        rng,
                    )
                    vals.append(m.t_total_s)
                    cf.append(m.contraflow_share)
                    succ.append(m.reunion_success_share)
                rows.append(
                    {
                        "reunion_timeout_ticks": timeout,
                        "reunion_timeout_s": timeout * cabin.dt_s,
                        "separation_rows": d,
                        "pct_separated": pct_separated,
                        "reunion_behavior": rb,
                        "seed": seed,
                        "n_iter": n_iter,
                        "t_total_s_mean": float(np.mean(vals)),
                        "t_total_s_sd": float(np.std(vals, ddof=1)),
                        "t_total_s_p50": float(np.median(vals)),
                        "contraflow_share_mean": float(np.mean(cf)),
                        "reunion_success_share_mean": float(np.mean(succ)),
                    }
                )
    return pd.DataFrame(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--n-iter", type=int, default=200)
    p.add_argument(
        "--timeouts",
        type=int,
        nargs="+",
        default=[20, 80, 200],
        help="reunion_timeout_ticks values (default 20, 80, 200)",
    )
    args = p.parse_args()

    df = run_timeout_sensitivity(
        timeout_levels=[int(x) for x in args.timeouts],
        separation_rows_levels=[0, 5, 10, 20],
        pct_separated=0.30,
        reunion_behaviors=["WAIT", "SEEK"],
        n_iter=int(args.n_iter),
        seed=int(args.seed),
    )
    paths = get_paths()
    paths.tables.mkdir(parents=True, exist_ok=True)
    out = paths.tables / "sensitivity_timeout.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
