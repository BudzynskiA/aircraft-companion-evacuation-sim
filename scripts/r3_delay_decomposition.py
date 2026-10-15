"""Decompose the WAIT delay at 30% separated pairs (Safety round-3, Reviewer 4).

For each seed, runs: no reunion (r = 0), partner held only, seeker movement
only, and full WAIT. The held-partner run uses the release ticks observed in
the matched full WAIT run.
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
    for d in [5, 10, 20]:
        for k in range(args.n_iter):
            s = args.seed + k
            log: dict = {}
            full = simulate_once(cabin, exits, agents, d, 0.30, "WAIT", np.random.default_rng(s), log=log)
            hold = simulate_once(
                cabin, exits, agents, d, 0.30, "WAIT", np.random.default_rng(s),
                mode="hold_only", hold_until_tick=log["release"],
            )
            seek = simulate_once(cabin, exits, agents, d, 0.30, "WAIT", np.random.default_rng(s), mode="seeker_only")
            none = simulate_once(cabin, exits, agents, d, 0.30, "WAIT", np.random.default_rng(s), reunion_probability=0.0)
            release_s = np.array(list(log["release"].values())) * cabin.dt_s
            rows.append(
                {
                    "separation_rows": d,
                    "iter": k,
                    "seed": s,
                    "t_total_none_s": none.t_total_s,
                    "t_total_hold_only_s": hold.t_total_s,
                    "t_total_seeker_only_s": seek.t_total_s,
                    "t_total_full_s": full.t_total_s,
                    "contraflow_full": full.contraflow_share,
                    "contraflow_seeker_only": seek.contraflow_share,
                    "reunion_success_full": full.reunion_success_share,
                    "partner_release_median_s": float(np.median(release_s)),
                    "partner_release_max_s": float(release_s.max()),
                }
            )
    df = pd.DataFrame(rows)
    out = get_paths().tables / "r3_delay_decomposition_runs.csv"
    df.to_csv(out, index=False)
    print(df.groupby("separation_rows").median(numeric_only=True).round(2).to_string())
    print(f"Wrote {out} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
