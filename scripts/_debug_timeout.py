"""Sensitivity of SEEK outcomes to the reunion timeout."""
import numpy as np

from simulate_evacuations import AgentConfig, CabinConfig, ExitConfig, simulate_once

cabin = CabinConfig()
exits = ExitConfig()

for ticks in [20, 80, 240]:
    agents = AgentConfig(reunion_timeout_ticks=ticks)
    for d in [5, 10, 20]:
        tt = []
        cf = []
        tot: dict[str, int] = {}
        for k in range(30):
            rng = np.random.default_rng(1 + k)
            trace: dict[str, int] = {}
            m = simulate_once(cabin, exits, agents, d, 0.30, "SEEK", rng, trace=trace)
            tt.append(m.t_total_s)
            cf.append(m.contraflow_share)
            for key, v in trace.items():
                tot[key] = tot.get(key, 0) + v
        p = max(1, tot.get("pairs", 0))
        print(
            f"SEEK timeout={ticks:3d} d={d:2d}: median={np.median(tt):6.1f} "
            f"contraflow={np.mean(cf):.4f} "
            f"reunited={tot.get('reunited', 0) / p:.2f} "
            f"dissolved={tot.get('dissolved', 0) / p:.2f} "
            f"timeout={tot.get('timeout', 0) / p:.2f}"
        )
