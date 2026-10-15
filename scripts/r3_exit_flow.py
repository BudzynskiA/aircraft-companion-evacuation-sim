"""Realised exit discharge rates in the default model (Safety round-3).

Reports, per exit and run, the mean flow over the central 80% of that exit's
discharge and the peak count in any 10 s window.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from _paths import get_paths
from simulate_evacuations import AgentConfig, CabinConfig, ExitConfig, simulate_once


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--n-iter", type=int, default=200)
    args = p.parse_args()

    cabin, exits, agents = CabinConfig(), ExitConfig(), AgentConfig()
    rows: list[dict] = []
    for d, pct, rb in [(0, 0.0, "WAIT"), (20, 0.30, "WAIT")]:
        for k in range(args.n_iter):
            log: dict = {}
            simulate_once(cabin, exits, agents, d, pct, rb, np.random.default_rng(args.seed + k), log=log)
            el = pd.DataFrame(log["exit_log"], columns=["t", "exit_idx"])
            for e, g in el.groupby("exit_idx"):
                t = np.sort(g["t"].to_numpy())
                lo, hi = np.quantile(t, [0.1, 0.9])
                n_core = int(((t >= lo) & (t <= hi)).sum())
                peak = max(int(((t >= x) & (t < x + 10.0)).sum()) for x in t) / 10.0
                rows.append(
                    {
                        "separation_rows": d,
                        "pct_separated": pct,
                        "reunion_behavior": rb,
                        "iter": k,
                        "exit_row": log["exit_positions"][int(e)],
                        "n_evacuated": len(t),
                        "core_flow_pax_s": n_core / (hi - lo) if hi > lo else np.nan,
                        "peak_10s_flow_pax_s": peak,
                    }
                )
    df = pd.DataFrame(rows)
    out = get_paths().tables / "r3_exit_flow.csv"
    df.to_csv(out, index=False)
    keys = ["pct_separated", "separation_rows"]
    print(df.groupby(keys)[["core_flow_pax_s", "peak_10s_flow_pax_s"]].describe(percentiles=[0.5, 0.95]).round(2).to_string())
    print(f"Wrote {out} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
