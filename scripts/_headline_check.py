import pandas as pd

from _paths import get_paths

paths = get_paths()
runs = pd.read_csv(paths.tables / "evac_v0_default_runs.csv")

med = (
    runs.groupby(["reunion_behavior", "pct_separated", "separation_rows"])
    .agg(
        t_total_med=("t_total_s", "median"),
        contraflow_med=("contraflow_share", "median"),
        contraflow_mean=("contraflow_share", "mean"),
        reunion_success=("reunion_success_share", "mean"),
    )
    .reset_index()
)

print("=== Median T_total (s) by separation x behavior, 30% separated ===")
sub = med[med["pct_separated"] == 0.30]
print(sub.pivot(index="separation_rows", columns="reunion_behavior", values="t_total_med"))

print()
print("=== Mean contraflow share, 30% separated ===")
print(sub.pivot(index="separation_rows", columns="reunion_behavior", values="contraflow_mean").round(4))

print()
print("=== Mean reunion success share, 30% separated ===")
print(sub.pivot(index="separation_rows", columns="reunion_behavior", values="reunion_success").round(3))

print()
print("=== Monotonicity check (median t_total vs separation), all pct levels ===")
for (rb, pct), g in med.groupby(["reunion_behavior", "pct_separated"]):
    g = g.sort_values("separation_rows")
    vals = g["t_total_med"].to_list()
    mono = all(b >= a - 1e-9 for a, b in zip(vals, vals[1:]))
    print(f"{rb} pct={pct}: {['%.1f' % v for v in vals]} monotonic={mono}")

print()
print("=== Full median table (all pct) ===")
print(
    med.pivot(index=["pct_separated", "separation_rows"], columns="reunion_behavior", values="t_total_med")
)
