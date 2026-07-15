"""Quick per-scenario smoke test with reunion outcome tracing."""
import numpy as np

from simulate_evacuations import AgentConfig, CabinConfig, ExitConfig, simulate_once

cabin = CabinConfig()
exits = ExitConfig()
agents = AgentConfig()

N = 30

for rb in ["WAIT", "SEEK"]:
    for d in [0, 5, 10, 20]:
        tot: dict[str, int] = {}
        tt = []
        cf = []
        for k in range(N):
            rng = np.random.default_rng(1 + k)
            trace: dict[str, int] = {}
            m = simulate_once(cabin, exits, agents, d, 0.30, rb, rng, trace=trace)
            tt.append(m.t_total_s)
            cf.append(m.contraflow_share)
            for key, v in trace.items():
                tot[key] = tot.get(key, 0) + v
        p = max(1, tot.get("pairs", 0))
        print(
            f"{rb} d={d:2d} pct=0.30: t_total median={np.median(tt):6.1f} "
            f"contraflow={np.mean(cf):.4f} pairs={tot.get('pairs', 0)} "
            f"reunited={tot.get('reunited', 0) / p:.2f} "
            f"dissolved={tot.get('dissolved', 0) / p:.2f} "
            f"timeout={tot.get('timeout', 0) / p:.2f}"
        )
