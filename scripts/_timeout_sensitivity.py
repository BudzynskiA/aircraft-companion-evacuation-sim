import numpy as np
import pandas as pd

from simulate_evacuations import AgentConfig, CabinConfig, ExitConfig, simulate_once

cabin = CabinConfig()
exits = ExitConfig()

for timeout in [20, 80, 200]:
    agents = AgentConfig(reunion_timeout_ticks=timeout)
    for d in [0, 5, 10, 20]:
        vals = []
        succ = []
        for k in range(40):
            rng = np.random.default_rng(1 + k)
            m = simulate_once(cabin, exits, agents, d, 0.30, "SEEK", rng)
            vals.append(m.t_total_s)
            succ.append(m.reunion_success_share)
        print(
            f"timeout={timeout:4d} sep={d:2d} SEEK 30%: "
            f"median t_total={np.median(vals):6.1f} mean success={np.mean(succ):.3f}"
        )
    print()
