from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
import pandas as pd

from _paths import get_paths


ReunionBehavior = Literal["WAIT", "SEEK"]


@dataclass(frozen=True)
class CabinConfig:
    n_rows: int = 30
    seats_per_row: int = 6
    dt_s: float = 0.25
    row_step_m: float = 0.8


@dataclass(frozen=True)
class ExitConfig:
    front: bool = True
    rear: bool = True
    overwing_rows: tuple[int, int] = (11, 12)
    exit_capacity_per_tick: int = 1


@dataclass(frozen=True)
class AgentConfig:
    premove_mean_s: float = 6.0
    premove_sd_s: float = 2.0
    speed_mean_m_s: float = 1.2
    speed_sd_m_s: float = 0.25
    speed_min_m_s: float = 0.4
    speed_max_m_s: float = 2.2
    # Reunion abandonment: if every movement attempt of the seeker is blocked
    # for this many consecutive ticks (default 20 ticks = 5 s at dt = 0.25 s),
    # the pair gives up on reunion and both members switch to independent
    # egress.
    reunion_timeout_ticks: int = 20


@dataclass(frozen=True)
class Scenario:
    separation_rows: int
    pct_separated: float
    reunion_behavior: ReunionBehavior
    seed: int
    n_iter: int = 200
    # Probability that a separated pair attempts reunion at all; pairs that
    # do not attempt reunion egress independently.
    reunion_probability: float = 1.0


@dataclass
class RunMetrics:
    t_total_s: float
    t50_s: float
    t90_s: float
    contraflow_share: float
    mean_blocked_attempts: float
    reunion_attempt_pairs: int
    reunion_success_share: float


def _clipped_normal(rng: np.random.Generator, mean: float, sd: float, lo: float, hi: float, size: int) -> np.ndarray:
    x = rng.normal(mean, sd, size=size)
    return np.clip(x, lo, hi)


def _build_exits(cabin: CabinConfig, exits: ExitConfig) -> list[int]:
    out: list[int] = []
    if exits.front:
        out.append(-1)
    if exits.rear:
        out.append(cabin.n_rows)
    for r in exits.overwing_rows:
        if 0 <= r < cabin.n_rows:
            out.append(r)
    out = sorted(set(out))
    assert len(out) > 0
    return out


def _distance_to_exit(row: int, exit_pos: int, n_rows: int) -> int:
    if exit_pos == -1:
        return row + 1
    if exit_pos == n_rows:
        return n_rows - row
    return abs(exit_pos - row)


def _direction_toward(row: int, target_row: int) -> int:
    if target_row < row:
        return -1
    if target_row > row:
        return 1
    return 0


def _nearest_exit(row: int, exit_positions: list[int], n_rows: int) -> tuple[int, int]:
    """Return (exit position, aisle target row) of the exit nearest to `row`."""
    best_e = exit_positions[0]
    best_d = _distance_to_exit(row, best_e, n_rows)
    for e in exit_positions[1:]:
        d = _distance_to_exit(row, e, n_rows)
        if d < best_d:
            best_e, best_d = e, d
    if best_e == -1:
        target = 0
    elif best_e == n_rows:
        target = n_rows - 1
    else:
        target = best_e
    return best_e, target


def simulate_once(
    cabin: CabinConfig,
    exits: ExitConfig,
    agents: AgentConfig,
    separation_rows: int,
    pct_separated: float,
    reunion_behavior: ReunionBehavior,
    rng: np.random.Generator,
    reunion_probability: float = 1.0,
    trace: dict[str, int] | None = None,
) -> RunMetrics:
    n_rows = cabin.n_rows
    n_agents = cabin.n_rows * cabin.seats_per_row

    exit_positions = _build_exits(cabin, exits)
    n_exits = len(exit_positions)

    base_rows = np.repeat(np.arange(n_rows, dtype=int), cabin.seats_per_row)
    assert base_rows.size == n_agents

    premove_s = _clipped_normal(rng, agents.premove_mean_s, agents.premove_sd_s, 0.0, 60.0, n_agents)
    speed = _clipped_normal(
        rng,
        agents.speed_mean_m_s,
        agents.speed_sd_m_s,
        agents.speed_min_m_s,
        agents.speed_max_m_s,
        n_agents,
    )

    in_aisle = np.zeros(n_agents, dtype=bool)
    evacuated = np.zeros(n_agents, dtype=bool)
    aisle_row = np.full(n_agents, -999, dtype=int)
    dist_acc = np.zeros(n_agents, dtype=float)

    occupants = np.full(n_rows, -1, dtype=int)
    # Number of agents currently occupying seat cells in each row (used to
    # check that a sidestepping seeker actually has a free seat cell).
    seat_count = np.zeros(n_rows, dtype=int)

    n_pairs = int(round(n_agents * pct_separated / 2.0))
    pair_of = np.full(n_agents, -1, dtype=int)
    is_seeker = np.zeros(n_agents, dtype=bool)
    reunion_active = np.zeros(n_agents, dtype=bool)
    reunited = np.zeros(n_agents, dtype=bool)
    stepped_aside = np.zeros(n_agents, dtype=bool)
    stall_ticks = np.zeros(n_agents, dtype=int)
    # Common exit chosen at reunion time so a reunited pair heads to the same
    # door instead of splitting on an exit-basin boundary (-999 = unset).
    joint_exit = np.full(n_agents, -999, dtype=int)

    pairs_a: np.ndarray = np.empty(0, dtype=int)
    pairs_b: np.ndarray = np.empty(0, dtype=int)
    if n_pairs > 0:
        # Pair selection by rejection sampling on the anchor row: partners are
        # drawn from agents already seated in the anchor row and in the row
        # exactly `separation_rows` aft, resampling the anchor until the full
        # nominal offset fits inside the cabin and both rows have free agents.
        # Seat occupancy is therefore identical across all scenarios; only the
        # behavioral labels differ, which removes the placement confound that
        # clipping the offset toward mid-cabin would introduce.
        free_by_row: list[list[int]] = [[] for _ in range(n_rows)]
        for k in range(n_agents):
            free_by_row[int(base_rows[k])].append(k)
        for row_agents in free_by_row:
            rng.shuffle(row_agents)

        a_list: list[int] = []
        b_list: list[int] = []
        attempts = 0
        while len(a_list) < n_pairs:
            attempts += 1
            assert attempts < 100_000, "pair placement rejection sampling did not converge"
            anchor = int(rng.integers(0, n_rows))
            partner_row = anchor + separation_rows
            if partner_row >= n_rows:
                continue
            if separation_rows == 0:
                if len(free_by_row[anchor]) < 2:
                    continue
                a_list.append(free_by_row[anchor].pop())
                b_list.append(free_by_row[anchor].pop())
            else:
                if not free_by_row[anchor] or not free_by_row[partner_row]:
                    continue
                a_list.append(free_by_row[anchor].pop())
                b_list.append(free_by_row[partner_row].pop())

        pairs_a = np.array(a_list, dtype=int)
        pairs_b = np.array(b_list, dtype=int)
        pair_of[pairs_a] = pairs_b
        pair_of[pairs_b] = pairs_a

        realized = np.abs(base_rows[pairs_a] - base_rows[pairs_b])
        assert np.all(realized == separation_rows), "realized separation != nominal separation"

        for i, j in zip(pairs_a, pairs_b, strict=True):
            if rng.random() < reunion_probability:
                reunion_active[i] = True
                reunion_active[j] = True
                seeker = int(i) if rng.random() < 0.5 else int(j)
                is_seeker[seeker] = True
                if trace is not None:
                    trace["pairs"] = trace.get("pairs", 0) + 1

    assert np.all((base_rows >= 0) & (base_rows < n_rows))

    for r in base_rows:
        seat_count[r] += 1

    evac_time_s = np.full(n_agents, np.nan, dtype=float)
    evac_count = 0

    blocked_attempts = 0
    enter_attempts = 0
    attempted_moves = 0
    exit_attempts = 0
    contraflow_ticks = 0

    max_ticks = int(math.ceil(1800.0 / cabin.dt_s))

    def _pair_pos(k: int) -> int:
        if in_aisle[k] or stepped_aside[k]:
            return int(aisle_row[k])
        return int(base_rows[k])

    def _trace(key: str) -> None:
        if trace is not None:
            trace[key] = trace.get(key, 0) + 1

    def _update_reunion_state() -> None:
        for i, j in zip(pairs_a, pairs_b, strict=True):
            if not reunion_active[i]:
                continue
            if evacuated[i] or evacuated[j]:
                reunion_active[i] = reunion_active[j] = False
                _trace("dissolved")
                continue
            d = abs(_pair_pos(int(i)) - _pair_pos(int(j)))
            if d <= 1:
                reunited[i] = reunited[j] = True
                reunion_active[i] = reunion_active[j] = False
                v = min(speed[i], speed[j])
                speed[i] = v
                speed[j] = v
                mid = (_pair_pos(int(i)) + _pair_pos(int(j))) // 2
                e, _ = _nearest_exit(mid, exit_positions, n_rows)
                joint_exit[i] = joint_exit[j] = e
                _trace("reunited")

    def _seeker_stalled(i: int) -> None:
        # Reunion timeout: a seeker whose every movement attempt has been
        # blocked for `reunion_timeout_ticks` consecutive ticks abandons the
        # reunion; both members then egress independently.
        stall_ticks[i] += 1
        if stall_ticks[i] >= agents.reunion_timeout_ticks:
            j = int(pair_of[i])
            reunion_active[i] = reunion_active[j] = False
            _trace("timeout")

    # Pairs already adjacent at seating (e.g. zero-row separation) reunite
    # immediately and egress together at the slower member's speed.
    _update_reunion_state()

    for t in range(max_ticks):
        now_s = t * cabin.dt_s

        exit_remaining = np.full(n_exits, exits.exit_capacity_per_tick, dtype=int)

        # Under WAIT, the non-seeker member of an active pair stays seated at
        # its own row (outside the aisle) until the seeker arrives.
        holding_seat = (
            (reunion_behavior == "WAIT")
            & reunion_active
            & (~is_seeker)
            & (~reunited)
            & (pair_of != -1)
        )

        want_enter = (~in_aisle) & (~evacuated) & (premove_s <= 0.0) & (~holding_seat)
        if np.any(want_enter):
            order = rng.permutation(np.flatnonzero(want_enter))
            for i in order:
                enter_attempts += 1
                r = int(aisle_row[i]) if stepped_aside[i] else int(base_rows[i])
                if occupants[r] == -1:
                    occupants[r] = i
                    in_aisle[i] = True
                    aisle_row[i] = r
                    stepped_aside[i] = False
                    seat_count[r] -= 1
                else:
                    blocked_attempts += 1
                    if stepped_aside[i] and reunion_active[i] and is_seeker[i]:
                        _seeker_stalled(int(i))

        active = np.flatnonzero(in_aisle & (~evacuated))
        if active.size == 0 and evac_count == n_agents:
            break

        premove_s = np.maximum(premove_s - cabin.dt_s, 0.0)
        dist_acc[active] += speed[active] * cabin.dt_s

        move_ready = active[dist_acc[active] >= cabin.row_step_m]
        if move_ready.size > 0:
            # Priority rule: exit-bound agents move before seekers, so the
            # evacuation outflow keeps the right of way in the aisle.
            seeking_mask = reunion_active[move_ready] & is_seeker[move_ready] & (~reunited[move_ready])
            exit_bound = rng.permutation(move_ready[~seeking_mask])
            seekers = rng.permutation(move_ready[seeking_mask])
            order = np.concatenate([exit_bound, seekers])
            for i in order:
                if evacuated[i]:
                    continue
                if not in_aisle[i]:
                    continue
                if dist_acc[i] < cabin.row_step_m:
                    continue

                r = int(aisle_row[i])
                seeking = bool(reunion_active[i] and is_seeker[i] and not reunited[i])
                nearest_e, nearest_target = _nearest_exit(r, exit_positions, n_rows)

                if seeking:
                    target_row = _pair_pos(int(pair_of[i]))
                    tgt_e = nearest_e
                elif joint_exit[i] != -999:
                    tgt_e = int(joint_exit[i])
                    if tgt_e == -1:
                        target_row = 0
                    elif tgt_e == n_rows:
                        target_row = n_rows - 1
                    else:
                        target_row = tgt_e
                else:
                    tgt_e = nearest_e
                    target_row = nearest_target

                step = _direction_toward(r, target_row)
                if step == 0:
                    if not seeking:
                        at_exit = False
                        exit_idx = None
                        if r in exit_positions:
                            at_exit = True
                            exit_idx = exit_positions.index(r)
                        if (tgt_e == -1 and r == 0) or (tgt_e == n_rows and r == n_rows - 1):
                            at_exit = True
                            exit_idx = exit_positions.index(tgt_e)

                        if at_exit and exit_idx is not None:
                            exit_attempts += 1
                            if exit_remaining[exit_idx] > 0:
                                exit_remaining[exit_idx] -= 1
                                occupants[r] = -1
                                in_aisle[i] = False
                                evacuated[i] = True
                                evac_time_s[i] = now_s
                                evac_count += 1
                                dist_acc[i] = 0.0
                                continue
                            blocked_attempts += 1
                            dist_acc[i] = cabin.row_step_m - 1e-9
                            continue

                    dist_acc[i] = 0.0
                    continue

                attempted_moves += 1
                # Contraflow: an agent-tick whose attempted step increases the
                # distance to that agent's nearest exit.
                if _distance_to_exit(r + step, nearest_e, n_rows) > _distance_to_exit(r, nearest_e, n_rows):
                    contraflow_ticks += 1

                next_r = r + step
                if next_r < 0:
                    next_r = 0
                if next_r >= n_rows:
                    next_r = n_rows - 1

                if occupants[next_r] == -1:
                    occupants[r] = -1
                    occupants[next_r] = i
                    aisle_row[i] = next_r
                    dist_acc[i] -= cabin.row_step_m
                    if dist_acc[i] < 0.0:
                        dist_acc[i] = 0.0
                    if seeking:
                        stall_ticks[i] = 0
                else:
                    blocked_attempts += 1
                    dist_acc[i] = cabin.row_step_m - 1e-9
                    if seeking:
                        _seeker_stalled(i)
                    if seeking and reunion_active[i] and seat_count[r] < cabin.seats_per_row:
                        # Deadlock resolution: a blocked seeker yields the
                        # aisle cell and steps aside into a free seat cell of
                        # its current row for a tick, then re-enters and
                        # continues toward the partner.
                        occupants[r] = -1
                        in_aisle[i] = False
                        stepped_aside[i] = True
                        seat_count[r] += 1

        _update_reunion_state()

        assert np.all((occupants == -1) | ((occupants >= 0) & (occupants < n_agents)))
        occ_ids = occupants[occupants != -1]
        if occ_ids.size > 1:
            assert np.unique(occ_ids).size == occ_ids.size

        if evac_count == n_agents:
            break

    assert evac_count == n_agents, "evacuation did not complete within max time"
    assert np.all(np.isfinite(evac_time_s)), "missing evacuation times"

    t_total_s = float(np.max(evac_time_s))
    t50_s = float(np.quantile(evac_time_s, 0.50))
    t90_s = float(np.quantile(evac_time_s, 0.90))

    contraflow_share = 0.0
    if attempted_moves > 0:
        contraflow_share = float(contraflow_ticks / attempted_moves)

    total_attempts = attempted_moves + enter_attempts + exit_attempts
    mean_blocked = float(blocked_attempts / max(1, total_attempts))

    attempt_pairs = int(np.count_nonzero(is_seeker))
    success_pairs = int(np.count_nonzero(reunited[pairs_a])) if pairs_a.size else 0
    success_share = float(success_pairs / attempt_pairs) if attempt_pairs > 0 else 0.0

    return RunMetrics(
        t_total_s=t_total_s,
        t50_s=t50_s,
        t90_s=t90_s,
        contraflow_share=contraflow_share,
        mean_blocked_attempts=mean_blocked,
        reunion_attempt_pairs=attempt_pairs,
        reunion_success_share=success_share,
    )


def run_monte_carlo(
    scenario: Scenario,
    cabin: CabinConfig | None = None,
    exits: ExitConfig | None = None,
    agents: AgentConfig | None = None,
) -> pd.DataFrame:
    cabin = cabin or CabinConfig()
    exits = exits or ExitConfig()
    agents = agents or AgentConfig()

    assert 0.0 <= scenario.pct_separated <= 1.0
    assert scenario.separation_rows >= 0
    assert 0.0 <= scenario.reunion_probability <= 1.0

    rows: list[dict[str, float | int | str]] = []
    for k in range(scenario.n_iter):
        rng = np.random.default_rng(scenario.seed + k)
        m = simulate_once(
            cabin=cabin,
            exits=exits,
            agents=agents,
            separation_rows=scenario.separation_rows,
            pct_separated=scenario.pct_separated,
            reunion_behavior=scenario.reunion_behavior,
            rng=rng,
            reunion_probability=scenario.reunion_probability,
        )
        rows.append(
            {
                "iter": k,
                "t_total_s": m.t_total_s,
                "t50_s": m.t50_s,
                "t90_s": m.t90_s,
                "contraflow_share": m.contraflow_share,
                "mean_blocked_attempts": m.mean_blocked_attempts,
                "reunion_attempt_pairs": m.reunion_attempt_pairs,
                "reunion_success_share": m.reunion_success_share,
            }
        )
    df = pd.DataFrame(rows)
    df["separation_rows"] = scenario.separation_rows
    df["pct_separated"] = scenario.pct_separated
    df["reunion_behavior"] = scenario.reunion_behavior
    df["reunion_probability"] = scenario.reunion_probability
    df["seed"] = scenario.seed
    df["n_iter"] = scenario.n_iter
    return df


def summarize_runs(df: pd.DataFrame) -> pd.DataFrame:
    group_cols = [
        "separation_rows",
        "pct_separated",
        "reunion_behavior",
        "reunion_probability",
        "seed",
        "n_iter",
    ]
    metric_cols = [
        "t_total_s",
        "t50_s",
        "t90_s",
        "contraflow_share",
        "mean_blocked_attempts",
        "reunion_success_share",
    ]

    def _agg(g: pd.DataFrame) -> pd.Series:
        out: dict[str, float] = {}
        for c in metric_cols:
            out[f"{c}_mean"] = float(g[c].mean())
            out[f"{c}_sd"] = float(g[c].std(ddof=1))
            out[f"{c}_p05"] = float(g[c].quantile(0.05))
            out[f"{c}_p50"] = float(g[c].quantile(0.50))
            out[f"{c}_p95"] = float(g[c].quantile(0.95))
        return pd.Series(out)

    summary = df.groupby(group_cols, as_index=False).apply(_agg).reset_index(drop=True)
    return summary


def write_outputs(summary: pd.DataFrame, runs: pd.DataFrame, tables_dir: Path, stem: str) -> tuple[Path, Path]:
    tables_dir.mkdir(parents=True, exist_ok=True)
    summary_path = tables_dir / f"{stem}_summary.csv"
    runs_path = tables_dir / f"{stem}_runs.csv"
    summary.to_csv(summary_path, index=False)
    runs.to_csv(runs_path, index=False)
    return summary_path, runs_path


def _plot_summary(summary: pd.DataFrame, figures_dir: Path, stem: str) -> list[Path]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []

    figures_dir.mkdir(parents=True, exist_ok=True)
    out_paths: list[Path] = []

    for metric in ["t_total_s_mean", "contraflow_share_mean", "mean_blocked_attempts_mean"]:
        fig, ax = plt.subplots(figsize=(8, 4))
        for rb in sorted(summary["reunion_behavior"].unique()):
            sub = summary[summary["reunion_behavior"] == rb]
            for pct in sorted(sub["pct_separated"].unique()):
                s2 = sub[sub["pct_separated"] == pct].sort_values("separation_rows")
                ax.plot(
                    s2["separation_rows"].to_numpy(),
                    s2[metric].to_numpy(),
                    marker="o",
                    label=f"{rb}, {int(round(100 * pct))}%",
                )
        ax.set_xlabel("Separation distance (rows)")
        ax.set_ylabel(metric.replace("_", " "))
        ax.grid(True, alpha=0.3)
        ax.legend(ncol=2, fontsize=8)
        fig.tight_layout()
        p = figures_dir / f"{stem}_{metric}.png"
        fig.savefig(p, dpi=160)
        plt.close(fig)
        out_paths.append(p)

    return out_paths


def run_experiment_set(
    separation_rows_levels: Iterable[int],
    pct_separated_levels: Iterable[float],
    reunion_behavior_levels: Iterable[ReunionBehavior],
    n_iter: int = 200,
    seed: int = 1,
    write_plots: bool = True,
    stem: str = "evac_v0",
    reunion_probability: float = 1.0,
) -> dict[str, object]:
    paths = get_paths()

    runs_all: list[pd.DataFrame] = []
    for rb in reunion_behavior_levels:
        for pct in pct_separated_levels:
            for d in separation_rows_levels:
                sc = Scenario(
                    separation_rows=int(d),
                    pct_separated=float(pct),
                    reunion_behavior=rb,
                    seed=int(seed),
                    n_iter=int(n_iter),
                    reunion_probability=float(reunion_probability),
                )
                df = run_monte_carlo(sc)
                runs_all.append(df)

    runs = pd.concat(runs_all, ignore_index=True)
    summary = summarize_runs(runs)

    summary_path, runs_path = write_outputs(summary, runs, paths.tables, stem=stem)
    fig_paths: list[Path] = []
    if write_plots:
        fig_paths = _plot_summary(summary, paths.figures, stem=stem)

    return {
        "summary": summary,
        "runs": runs,
        "summary_csv": summary_path,
        "runs_csv": runs_path,
        "figures": fig_paths,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--n-iter", type=int, default=200)
    p.add_argument("--plots", action="store_true")
    p.add_argument("--stem", type=str, default="evac_v0")
    p.add_argument("--reunion", type=str, choices=["WAIT", "SEEK", "BOTH"], default="BOTH")
    p.add_argument("--reunion-probability", type=float, default=1.0)
    args = p.parse_args()

    reunion_levels: list[ReunionBehavior]
    if args.reunion == "BOTH":
        reunion_levels = ["WAIT", "SEEK"]
    else:
        reunion_levels = [args.reunion]  # type: ignore[list-item]

    run_experiment_set(
        separation_rows_levels=[0, 5, 10, 20],
        pct_separated_levels=[0.0, 0.10, 0.30],
        reunion_behavior_levels=reunion_levels,
        n_iter=int(args.n_iter),
        seed=int(args.seed),
        write_plots=bool(args.plots),
        stem=str(args.stem),
        reunion_probability=float(args.reunion_probability),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
