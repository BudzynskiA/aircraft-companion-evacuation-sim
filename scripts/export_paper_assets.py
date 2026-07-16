"""Export manuscript figures and table01 subset from existing summary CSV."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from _paths import get_paths

PAPER_ROOT = (
    Path(__file__).resolve().parents[3]
    / "04_papers"
    / "journal_articles"
    / "2026"
    / "separate_passengers_aircraft_safety"
)
PAPER_FIGURES = PAPER_ROOT / "presubmission" / "figures"
PAPER_TABLES = PAPER_ROOT / "presubmission" / "tables"

HEADLINE_PCT = 0.3
SEPARATIONS = [0, 5, 10, 20]


def _paper_subset(summary: pd.DataFrame) -> pd.DataFrame:
    sub = summary[
        (summary["pct_separated"] == HEADLINE_PCT)
        & (summary["separation_rows"].isin(SEPARATIONS))
    ].copy()
    sub["t_total_median_s"] = sub["t_total_s_p50"]
    cols = [
        "separation_rows",
        "pct_separated",
        "reunion_behavior",
        "n_iter",
        "seed",
        "t_total_median_s",
        "contraflow_share_mean",
        "reunion_success_share_mean",
    ]
    return sub[cols].sort_values(["separation_rows", "reunion_behavior"])


def _plot_line(
    df: pd.DataFrame,
    y_col: str,
    ylabel: str,
    out_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    for rb in ("WAIT", "SEEK"):
        s = df[df["reunion_behavior"] == rb].sort_values("separation_rows")
        ax.plot(
            s["separation_rows"],
            s[y_col],
            marker="o",
            label=rb,
        )
    ax.set_xlabel("Separation distance (rows)")
    ax.set_ylabel(ylabel)
    ax.set_xticks(SEPARATIONS)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def _plot_wait_vs_seek(df: pd.DataFrame, out_path: Path) -> None:
    wait = df[df["reunion_behavior"] == "WAIT"].sort_values("separation_rows")
    seek = df[df["reunion_behavior"] == "SEEK"].sort_values("separation_rows")
    x = range(len(SEPARATIONS))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - width / 2 for i in x], wait["t_total_median_s"], width, label="WAIT")
    ax.bar([i + width / 2 for i in x], seek["t_total_median_s"], width, label="SEEK")
    ax.set_xlabel("Separation distance (rows)")
    ax.set_ylabel("Median T_total (s)")
    ax.set_xticks(list(x))
    ax.set_xticklabels([str(s) for s in SEPARATIONS])
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> int:
    paths = get_paths()
    summary_path = paths.tables / "evac_v0_default_summary.csv"
    if not summary_path.is_file():
        raise SystemExit(f"Missing summary CSV: {summary_path}")

    summary = pd.read_csv(summary_path)
    headline = _paper_subset(summary)

    PAPER_FIGURES.mkdir(parents=True, exist_ok=True)
    PAPER_TABLES.mkdir(parents=True, exist_ok=True)

    _plot_line(
        headline,
        "t_total_median_s",
        "Median T_total (s)",
        PAPER_FIGURES / "fig01_t_total_median.png",
    )
    _plot_line(
        headline,
        "contraflow_share_mean",
        "Mean contraflow share",
        PAPER_FIGURES / "fig02_contraflow_share.png",
    )
    _plot_wait_vs_seek(headline, PAPER_FIGURES / "fig03_wait_vs_seek_30pct.png")

    table_path = PAPER_TABLES / "table01_scenario_summary.csv"
    headline.to_csv(table_path, index=False)
    print(f"Wrote {table_path}")
    for name in (
        "fig01_t_total_median.png",
        "fig02_contraflow_share.png",
        "fig03_wait_vs_seek_30pct.png",
    ):
        print(f"Wrote {PAPER_FIGURES / name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
