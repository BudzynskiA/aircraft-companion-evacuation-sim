"""Exit admission ceiling sensitivity: 4, 2 and 1 pax/s per exit (Safety round-3)."""

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
    for interval in [1, 2, 4]:
        for d, pct in [(0, 0.0), (0, 0.30), (5, 0.30), (10, 0.30), (20, 0.30)]:
            for rb in (["WAIT", "SEEK"] if pct > 0 else ["WAIT"]):
                for k in range(args.n_iter):
                    m = simulate_once(
                        cabin, exits, agents, d, pct, rb, np.random.default_rng(args.seed + k),
                        exit_interval_ticks=interval,
                    )
                    rows.append(
                        {
                            "exit_cap_pax_s": 1.0 / (interval * cabin.dt_s),
                            "separation_rows": d,
                            "pct_separated": pct,
                            "reunion_behavior": rb,
                            "iter": k,
                            "t_total_s": m.t_total_s,
                            "t50_s": m.t50_s,
                            "t90_s": m.t90_s,
                            "contraflow_share": m.contraflow_share,
                            "reunion_success_share": m.reunion_success_share,
                        }
                    )
    df = pd.DataFrame(rows)
    out = get_paths().tables / "r3_exit_capacity_runs.csv"
    df.to_csv(out, index=False)
    keys = ["exit_cap_pax_s", "pct_separated", "reunion_behavior", "separation_rows"]
    print(df.groupby(keys)["t_total_s"].median().to_string())
    print(f"Wrote {out} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
