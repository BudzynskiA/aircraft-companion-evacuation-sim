# Aircraft cabin evacuation simulation (v0)

Minimal, portable pipeline for a narrow-body single-aisle cabin evacuation experiment set.

## Setup

From the repository root:

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Run (one command)

From the repository root:

```bash
.\.venv\Scripts\python scripts\run_all.py --plots
```

## Outputs

- `tables/evac_v0_default_summary.csv`: scenario-level summary (means, SD, percentiles)
- `tables/evac_v0_default_runs.csv`: per-run metrics (for diagnostics and additional plots)
- `figures/evac_v0_default_*.png`: a few basic plots (enabled with `--plots`)

## Experiment defaults

- Cabin: 30 rows, 3-aisle-3 seats, single aisle
- Exits: front, rear, and an overwing pair (configurable in `scripts/simulate_evacuations.py`)
- Separation distance: 0, 5, 10, 20 rows
- Percent separated: 0%, 10%, 30%
- Reunion behavior: `WAIT` vs `SEEK`
- Monte Carlo iterations: 200 per scenario

## Pair and reunion model

- Pair placement uses rejection sampling: the anchor row is redrawn until the
  full nominal offset fits inside the cabin, so realized separation always
  equals nominal separation (asserted per pair).
- One member of each pair is designated the seeker. Under `WAIT` the other
  member stays at its own row until the seeker arrives; under `SEEK` the other
  member proceeds toward its nearest exit while the seeker moves toward it.
- The seeker physically moves along the aisle toward the partner's row,
  against the evacuation outflow if needed. Exit-bound agents have aisle
  priority; a blocked seeker steps aside into the seat area of its current row
  for a tick, then re-enters and continues.
- `reunion_timeout_ticks` (default 20; `AgentConfig`): if the seeker makes no
  net progress toward its partner for this many consecutive ticks (5 s at
  dt = 0.25 s), the pair abandons reunion and both egress independently.
- Reunion completes when partners occupy adjacent cells; afterwards both move
  at the slower member's speed to the exit.
- `reunion_probability` (default 1.0; `Scenario` / `--reunion-probability`):
  probability that a separated pair attempts reunion at all.
- Contraflow metric: share of attempted moves that increase the agent's
  distance to its nearest exit.

## Reproducibility

Use `--seed` to control the random seed base. Each iteration uses `seed + iter`.

## Citation and license

- **How to cite:** see [`CITATION.cff`](CITATION.cff) (Citation File Format). When the companion journal article is published, cite that paper as the primary reference and this repository for code reproduction.
- **License:** [MIT](LICENSE). Chosen for compatibility with Elsevier *Safety Science* data/code sharing expectations (software supplementary material; no restriction on academic reuse). Simulation outputs are synthetic; no third-party data.

**Companion paper (in preparation):** proposed citekey `companion_separation_evacuation`; target journal TBD. Manuscript materials are not shipped in this repository.

**Public release:** intended standalone repo `aircraft-companion-evacuation-sim`. **Publish boundary:** only this folder may be pushed to GitHub; never run `git`/`gh` from `personal_cloud/` root. See [`GITHUB_PUBLISH.md`](GITHUB_PUBLISH.md) and run `python scripts/verify_publish_scope.py` before every push.

## Sensitivity exports

```bash
.\.venv\Scripts\python scripts\run_sensitivity.py --seed 1
```

Writes `tables/sensitivity_timeout.csv` and `tables/sensitivity_reunion_prob.csv` (same seeds as the default experiment set).

## Round-3 reviewer analyses (Safety 4491459, 2026-10-14)

`simulate_once` has optional arguments (`mode`, `hold_until_tick`, `log`, `exit_interval_ticks`); the defaults reproduce the published runs exactly.

```bash
.\.venv\Scripts\python scripts\r3_delay_decomposition.py   # tables/r3_delay_decomposition_runs.csv
.\.venv\Scripts\python scripts\r3_exit_flow.py             # tables/r3_exit_flow.csv
.\.venv\Scripts\python scripts\r3_exit_capacity.py         # tables/r3_exit_capacity_runs.csv
```

- Delay decomposition (WAIT, 30% separated, 5/10/20 rows): no reunion vs partner held only vs seeker movement only vs full WAIT.
- Exit flow: realised discharge per exit (central 80% of discharge; peak 10 s window).
- Exit capacity: admission ceiling of 4, 2 and 1 pax/s per exit.
