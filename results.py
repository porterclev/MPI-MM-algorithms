import csv
import math
import os
from pathlib import Path
from collections import defaultdict

# ── try to import plotting libs ──────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False
    print("matplotlib/numpy not found. Install with:")
    print("  pip3 install matplotlib numpy --user")
    raise SystemExit(1)

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False
    print("seaborn not found, using plain matplotlib. Install with:")
    print("  pip3 install seaborn --user")

ANALYSIS_CSV = Path("./csvs/shape_analysis.csv")
COMBINED_CSV = Path("./csvs/combined_results.csv")
GRAPH_DIR    = Path("./analysis_graphs")
GRAPH_DIR.mkdir(parents=True, exist_ok=True)
RANKING_PATH = GRAPH_DIR / "shape_rankings.txt"

IMPL_COLORS = {
    "Implementation 1 (Serial)": "#1d4ed8",
    "Implementation 2 (MM-1D)":  "#ea580c",
    "Implementation 3 (MM-2D)":  "#059669",
}

SHAPE_COLORS = {
    "uniform":              "#7c3aed",
    "n_dominant":           "#dc2626",
    "m_dominant":           "#d97706",
    "q_dominant":           "#0891b2",
    "square_outer":         "#16a34a",
    "square_outer_large_n": "#db2777",
    "mixed":                "#6b7280",
    "unknown":              "#9ca3af",
}

P_MARKERS = {1: "o", 4: "s", 9: "^", 16: "D", 25: "P"}


def load_csv(path):
    rows = []
    with open(str(path), newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def safe_float(val, default=None):
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def safe_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def save(fig, name):
    path = GRAPH_DIR / (name + ".png")
    fig.savefig(str(path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved: " + str(path))


def build_shape_bucket_stats(rows):
    """
    Build one aggregated row per (implementation, shape_type, p).

    For speedup, use a consistent bucket baseline:
        aggregate_speedup = sum(p1_seconds for cases in bucket) / sum(parallel_seconds)

    This avoids averaging together per-case speedups that were each computed
    against different p=1 runtimes.
    """
    serial_impl = "Implementation 1 (Serial)"
    baseline_lookup = {}

    for r in rows:
        if r.get("implementation") == serial_impl or r.get("status") != "ok":
            continue

        impl = r.get("implementation")
        m = safe_int(r.get("m"))
        n = safe_int(r.get("n"))
        q = safe_int(r.get("q"))
        p = safe_int(r.get("p"))
        seconds = safe_float(r.get("seconds"))
        if None in (impl, m, n, q, p) or seconds is None or p != 1:
            continue

        baseline_lookup[(impl, m, n, q)] = seconds

    buckets = defaultdict(lambda: {
        "baseline_seconds_sum": 0.0,
        "parallel_seconds_sum": 0.0,
        "cost_sum": 0.0,
        "total_ops_sum": 0.0,
        "sample_count": 0,
    })

    for r in rows:
        if r.get("implementation") == serial_impl or r.get("status") != "ok":
            continue

        impl = r.get("implementation")
        shape = r.get("shape_type", "unknown")
        m = safe_int(r.get("m"))
        n = safe_int(r.get("n"))
        q = safe_int(r.get("q"))
        p = safe_int(r.get("p"))
        seconds = safe_float(r.get("seconds"))
        cost = safe_float(r.get("cost"))
        total_ops = safe_int(r.get("total_ops"))

        if None in (impl, shape, m, n, q, p, total_ops) or seconds is None or cost is None:
            continue

        baseline_seconds = baseline_lookup.get((impl, m, n, q))
        if baseline_seconds is None:
            continue

        bucket = buckets[(impl, shape, p)]
        bucket["baseline_seconds_sum"] += baseline_seconds
        bucket["parallel_seconds_sum"] += seconds
        bucket["cost_sum"] += cost
        bucket["total_ops_sum"] += total_ops
        bucket["sample_count"] += 1

    bucket_rows = []
    for (impl, shape, p), data in sorted(buckets.items()):
        count = data["sample_count"]
        parallel_sum = data["parallel_seconds_sum"]
        baseline_sum = data["baseline_seconds_sum"]
        total_ops_sum = data["total_ops_sum"]
        if count == 0 or parallel_sum <= 0.0 or total_ops_sum <= 0.0:
            continue

        bucket_rows.append({
            "implementation": impl,
            "shape_type": shape,
            "p": p,
            "avg_baseline_seconds": baseline_sum / count,
            "avg_seconds": parallel_sum / count,
            "avg_cost": data["cost_sum"] / count,
            "seconds_per_gop": (parallel_sum * 1.0e9) / total_ops_sum,
            "cost_per_gop": (data["cost_sum"] * 1.0e9) / total_ops_sum,
            "aggregate_speedup": baseline_sum / parallel_sum,
            "sample_count": count,
        })

    return bucket_rows


def summarize_failures(rows):
    counts = defaultdict(lambda: {"ok": 0, "failed": 0})

    for r in rows:
        impl = r.get("implementation", "unknown")
        p = safe_int(r.get("p"))
        if p is None:
            continue
        key = (impl, p)
        if r.get("status") == "ok":
            counts[key]["ok"] += 1
        else:
            counts[key]["failed"] += 1

    print("\nFailure summary by implementation and P:")
    saw_failure = False
    for (impl, p), data in sorted(counts.items()):
        total = data["ok"] + data["failed"]
        if total == 0:
            continue
        fail_rate = data["failed"] / total
        label = "WARNING" if data["failed"] else "OK"
        if data["failed"]:
            saw_failure = True
        print(
            "  {label:<7} {impl:<24} P={p:<2} failures={failed}/{total} ({rate:.1%})".format(
                label=label,
                impl=impl[:24],
                p=p,
                failed=data["failed"],
                total=total,
                rate=fail_rate,
            )
        )

    if not saw_failure:
        print("  No failed rows found in combined results.")


def report_suspicious_scaling(rows, limit=12):
    suspicious = []
    serial_impl = "Implementation 1 (Serial)"

    for r in rows:
        if r.get("implementation") == serial_impl or r.get("status") != "ok":
            continue

        p = safe_int(r.get("p"))
        speedup = safe_float(r.get("speedup"))
        serial_speedup = safe_float(r.get("serial_speedup"))
        m = safe_int(r.get("m"))
        n = safe_int(r.get("n"))
        q = safe_int(r.get("q"))
        seconds = safe_float(r.get("seconds"))
        if None in (p, speedup, m, n, q, seconds) or p <= 1:
            continue

        ratio = speedup / p
        serial_ratio = (serial_speedup / p) if serial_speedup is not None else None
        if ratio > 1.05 or (serial_ratio is not None and serial_ratio > 1.10):
            suspicious.append({
                "implementation": r.get("implementation"),
                "m": m,
                "n": n,
                "q": q,
                "p": p,
                "seconds": seconds,
                "speedup": speedup,
                "serial_speedup": serial_speedup,
                "ratio": max(ratio, serial_ratio or ratio),
            })

    suspicious.sort(key=lambda row: row["ratio"], reverse=True)

    print("\nSuspicious scaling rows:")
    if not suspicious:
        print("  No rows exceeded the superlinear warning thresholds.")
        return

    for row in suspicious[:limit]:
        print(
            "  {impl} m={m} n={n} q={q} p={p} "
            "speedup={speedup:.2f} serial_speedup={serial_speedup} seconds={seconds:.3f}".format(
                impl=row["implementation"],
                m=row["m"],
                n=row["n"],
                q=row["q"],
                p=row["p"],
                speedup=row["speedup"],
                serial_speedup=(
                    "{:.2f}".format(row["serial_speedup"])
                    if row["serial_speedup"] is not None else "-"
                ),
                seconds=row["seconds"],
            )
        )


def rank_shapes_by_metric(rows, metric_key, metric_label, higher_is_better):
    targets = ["Implementation 2 (MM-1D)", "Implementation 3 (MM-2D)"]
    sections = []

    for impl in targets:
        subrows = [r for r in rows
                   if r["implementation"] == impl
                   and safe_float(r.get(metric_key)) is not None
                   and safe_int(r.get("p")) is not None]

        by_p = defaultdict(list)
        for r in subrows:
            by_p[safe_int(r["p"])].append((r["shape_type"], safe_float(r[metric_key])))

        if not by_p:
            continue

        shape_stats = defaultdict(lambda: {
            "ranks": [],
            "values": [],
            "p_values": [],
        })
        p_rankings = []

        for p in sorted(by_p):
            ranked = sorted(
                by_p[p],
                key=lambda item: item[1],
                reverse=higher_is_better,
            )
            p_rankings.append((p, ranked))

            for rank, (shape, value) in enumerate(ranked, start=1):
                shape_stats[shape]["ranks"].append(rank)
                shape_stats[shape]["values"].append(value)
                shape_stats[shape]["p_values"].append(p)

        overall = []
        for shape, stats in shape_stats.items():
            avg_rank = sum(stats["ranks"]) / len(stats["ranks"])
            avg_value = sum(stats["values"]) / len(stats["values"])
            overall.append({
                "shape": shape,
                "avg_rank": avg_rank,
                "avg_value": avg_value,
                "p_values": sorted(stats["p_values"]),
                "count": len(stats["ranks"]),
            })

        overall.sort(
            key=lambda item: (
                item["avg_rank"],
                -item["avg_value"] if higher_is_better else item["avg_value"],
                item["shape"],
            )
        )

        lines = []
        lines.append(metric_label + " ranking  |  " + impl)
        lines.append("  Overall rank uses average placement across available P values.")
        direction = "higher is better" if higher_is_better else "lower is better"
        lines.append("  Metric direction: " + direction)
        for idx, item in enumerate(overall, start=1):
            lines.append(
                "  {rank}. {shape:<22} avg_rank={avg_rank:.2f} avg_value={avg_value:.6f} P={p_values}".format(
                    rank=idx,
                    shape=item["shape"],
                    avg_rank=item["avg_rank"],
                    avg_value=item["avg_value"],
                    p_values=",".join(str(p) for p in item["p_values"]),
                )
            )

        lines.append("  Per-P ordering:")
        for p, ranked in p_rankings:
            parts = [
                "{shape} ({value:.6f})".format(shape=shape, value=value)
                for shape, value in ranked
            ]
            lines.append("    P={p}: ".format(p=p) + " > ".join(parts))

        sections.append("\n".join(lines))

    return sections


def report_shape_rankings(rows):
    metric_configs = [
        ("avg_seconds", "P vs Runtime", False),
        ("avg_cost", "P vs Cost", False),
        ("aggregate_speedup", "P vs Speedup", True),
    ]

    sections = []
    for metric_key, metric_label, higher_is_better in metric_configs:
        sections.extend(
            rank_shapes_by_metric(rows, metric_key, metric_label, higher_is_better)
        )

    if not sections:
        print("\nShape rankings:")
        print("  No ranking data available.")
        return

    report = "\n\n".join(sections)
    print("\nShape rankings:")
    print(report)
    RANKING_PATH.write_text(report + "\n")
    print("\nSaved: " + str(RANKING_PATH))


# ── 1. Line plot: total_ops vs seconds by shape_type ────────────────────────
def plot_ops_vs_seconds(rows):
    targets = ["Implementation 2 (MM-1D)", "Implementation 3 (MM-2D)"]
    p_values = sorted(set(safe_int(r["p"]) for r in rows if safe_int(r["p"]) is not None))

    for p in p_values:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=False)
        fig.suptitle("Total Ops vs Runtime  |  P=" + str(p), fontsize=13)

        for ax, impl in zip(axes, targets):
            subrows = [r for r in rows
                       if r["implementation"] == impl
                       and safe_int(r["p"]) == p
                       and safe_float(r["avg_seconds"]) is not None]

            # group by shape_type
            by_shape = defaultdict(list)
            for r in subrows:
                ops = safe_int(r["total_ops"])
                sec = safe_float(r["avg_seconds"])
                if ops is not None and sec is not None:
                    by_shape[r["shape_type"]].append((ops, sec))

            for shape, points in sorted(by_shape.items()):
                points.sort(key=lambda x: x[0])
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                color = SHAPE_COLORS.get(shape, "#999")
                ax.plot(xs, ys, marker="o", markersize=4, linewidth=1.5,
                        label=shape, color=color)

            ax.set_title(impl.replace("Implementation ", "Impl "), fontsize=11)
            ax.set_xlabel("Total ops (2·m·n·q)")
            ax.set_ylabel("Avg seconds")
            ax.legend(fontsize=8, loc="upper left")
            ax.grid(True, linestyle="--", alpha=0.4)
            ax.ticklabel_format(style="sci", axis="x", scilimits=(0, 0))

        plt.tight_layout()
        save(fig, "ops_vs_seconds_p" + str(p))


# ── 2. Line plot: normalized runtime vs total_ops by shape_type ──────────────
def plot_ops_vs_normalized_runtime(rows):
    targets = ["Implementation 2 (MM-1D)", "Implementation 3 (MM-2D)"]
    p_values = sorted(set(safe_int(r["p"]) for r in rows if safe_int(r["p"]) is not None))

    for p in p_values:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=False)
        fig.suptitle("Total Ops vs Normalized Runtime  |  P=" + str(p), fontsize=13)

        for ax, impl in zip(axes, targets):
            subrows = [r for r in rows
                       if r["implementation"] == impl
                       and safe_int(r["p"]) == p
                       and safe_float(r["avg_seconds"]) is not None
                       and safe_int(r["total_ops"]) not in (None, 0)]

            by_shape = defaultdict(list)
            for r in subrows:
                ops = safe_int(r["total_ops"])
                sec = safe_float(r["avg_seconds"])
                if ops is not None and ops > 0 and sec is not None:
                    by_shape[r["shape_type"]].append((ops, (sec * 1.0e9) / ops))

            for shape, points in sorted(by_shape.items()):
                points.sort(key=lambda x: x[0])
                xs = [point[0] for point in points]
                ys = [point[1] for point in points]
                ax.plot(xs, ys, marker="o", markersize=4, linewidth=1.5,
                        label=shape, color=SHAPE_COLORS.get(shape, "#999"))

            ax.set_title(impl.replace("Implementation ", "Impl "), fontsize=11)
            ax.set_xlabel("Total ops (2·m·n·q)")
            ax.set_ylabel("Seconds per GOp")
            ax.legend(fontsize=8, loc="upper left")
            ax.grid(True, linestyle="--", alpha=0.4)
            ax.ticklabel_format(style="sci", axis="x", scilimits=(0, 0))

        plt.tight_layout()
        save(fig, "ops_vs_normalized_runtime_p" + str(p))


# ── 3. Bar chart: speedup by shape_type per implementation ───────────────────
def plot_speedup_by_shape(rows):
    targets = ["Implementation 2 (MM-1D)", "Implementation 3 (MM-2D)"]
    p_values = sorted(set(safe_int(r["p"]) for r in rows if safe_int(r["p"]) is not None))

    for p in p_values:
        data = {}
        for r in rows:
            if safe_int(r["p"]) != p:
                continue
            if r["implementation"] not in targets:
                continue
            sp = safe_float(r.get("aggregate_speedup"))
            if sp is None:
                continue
            data[(r["implementation"], r["shape_type"])] = sp

        all_shapes = sorted(set(shape for (_impl, shape) in data))
        if not all_shapes:
            continue

        x = list(range(len(all_shapes)))
        width = 0.35
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.suptitle("Aggregate Speedup by Shape Type  |  P=" + str(p) + "  |  baseline=P=1", fontsize=13)

        for i, impl in enumerate(targets):
            vals = [data.get((impl, s), 0.0) for s in all_shapes]
            offset = (i - 0.5) * width
            bars = ax.bar([xi + offset for xi in x], vals, width,
                          label=impl, color=IMPL_COLORS.get(impl, "#888"),
                          alpha=0.85, edgecolor="white")
            for bar, val in zip(bars, vals):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 0.01,
                            "{:.2f}".format(val),
                            ha="center", va="bottom", fontsize=7)

        ax.axhline(1.0, color="#374151", linewidth=1, linestyle="--", label="Speedup=1 (baseline)")
        ax.set_xticks(x)
        ax.set_xticklabels(all_shapes, rotation=20, ha="right", fontsize=9)
        ax.set_ylabel("Aggregate Speedup over P=1")
        ax.set_xlabel("Shape Type")
        ax.legend(fontsize=9)
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)
        plt.tight_layout()
        save(fig, "speedup_by_shape_p" + str(p))


# ── 4. Scatter: cost vs total_ops colored by shape_type ─────────────────────
def plot_cost_scatter(rows):
    targets = ["Implementation 2 (MM-1D)", "Implementation 3 (MM-2D)"]
    p_values = sorted(set(safe_int(r["p"]) for r in rows if safe_int(r["p"]) is not None))

    for p in p_values:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=False)
        fig.suptitle("Cost vs Total Ops  |  P=" + str(p), fontsize=13)

        for ax, impl in zip(axes, targets):
            subrows = [r for r in rows
                       if r["implementation"] == impl
                       and safe_int(r["p"]) == p
                       and safe_float(r.get("avg_cost")) is not None
                       and safe_int(r.get("total_ops")) is not None]

            by_shape = defaultdict(list)
            for r in subrows:
                by_shape[r["shape_type"]].append(
                    (safe_int(r["total_ops"]), safe_float(r["avg_cost"]))
                )

            for shape, points in sorted(by_shape.items()):
                xs = [pt[0] for pt in points]
                ys = [pt[1] for pt in points]
                ax.scatter(xs, ys, label=shape, s=40, alpha=0.75,
                           color=SHAPE_COLORS.get(shape, "#999"), edgecolors="none")

            ax.set_title(impl.replace("Implementation ", "Impl "), fontsize=11)
            ax.set_xlabel("Total ops (2·m·n·q)")
            ax.set_ylabel("Cost  (P × seconds)")
            ax.legend(fontsize=8, loc="upper left")
            ax.grid(True, linestyle="--", alpha=0.4)
            ax.ticklabel_format(style="sci", axis="both", scilimits=(0, 0))

        plt.tight_layout()
        save(fig, "cost_scatter_p" + str(p))


# ── 5. Heatmap: m vs q, color = speedup (one per impl, per p, fix n) ─────────
def plot_speedup_heatmap(rows):
    targets = ["Implementation 2 (MM-1D)", "Implementation 3 (MM-2D)"]
    p_values = sorted(set(safe_int(r["p"]) for r in rows if safe_int(r["p"]) is not None))
    n_values = sorted(set(safe_int(r["n"]) for r in rows if safe_int(r["n"]) is not None))

    if not n_values:
        return

    # pick the median n to keep the heatmap focused
    median_n = n_values[len(n_values) // 2]

    for p in p_values:
        for impl in targets:
            subrows = [r for r in rows
                       if r["implementation"] == impl
                       and safe_int(r["p"]) == p
                       and safe_int(r["n"]) == median_n
                       and safe_float(r.get("avg_speedup")) is not None]

            if len(subrows) < 2:
                continue

            m_vals = sorted(set(safe_int(r["m"]) for r in subrows))
            q_vals = sorted(set(safe_int(r["q"]) for r in subrows))

            if len(m_vals) < 2 or len(q_vals) < 2:
                continue

            grid = np.full((len(m_vals), len(q_vals)), np.nan)
            m_idx = {v: i for i, v in enumerate(m_vals)}
            q_idx = {v: i for i, v in enumerate(q_vals)}

            for r in subrows:
                mi = m_idx.get(safe_int(r["m"]))
                qi = q_idx.get(safe_int(r["q"]))
                sp = safe_float(r["avg_speedup"])
                if mi is not None and qi is not None and sp is not None:
                    grid[mi][qi] = sp

            fig, ax = plt.subplots(figsize=(8, 6))
            label = impl.replace("Implementation ", "Impl ")
            fig.suptitle(
                "Speedup Heatmap  |  " + label + "  |  P=" + str(p) + "  |  n=" + str(median_n) + "  |  baseline=P=1",
                fontsize=12
            )

            cmap = "RdYlGn"
            im = ax.imshow(grid, aspect="auto", cmap=cmap, origin="lower",
                           vmin=0, vmax=max(2.0, float(np.nanmax(grid))))
            plt.colorbar(im, ax=ax, label="Speedup over P=1")

            ax.set_xticks(range(len(q_vals)))
            ax.set_xticklabels([str(v) for v in q_vals], fontsize=8)
            ax.set_yticks(range(len(m_vals)))
            ax.set_yticklabels([str(v) for v in m_vals], fontsize=8)
            ax.set_xlabel("q  (cols of B / C)")
            ax.set_ylabel("m  (rows of A / C)")

            # annotate cells
            for i in range(len(m_vals)):
                for j in range(len(q_vals)):
                    val = grid[i][j]
                    if not np.isnan(val):
                        ax.text(j, i, "{:.2f}".format(val),
                                ha="center", va="center", fontsize=7,
                                color="black")

            plt.tight_layout()
            impl_tag = "1d" if "1D" in impl else "2d"
            save(fig, "heatmap_speedup_" + impl_tag + "_p" + str(p) + "_n" + str(median_n))


# ── 6. Line plots: P vs metric per shape_type ────────────────────────────────
def plot_p_vs_metric(rows, metric_key, title_text, y_label, filename_prefix, baseline=None):
    targets = ["Implementation 2 (MM-1D)", "Implementation 3 (MM-2D)"]

    for impl in targets:
        subrows = [r for r in rows
                   if r["implementation"] == impl
                   and safe_float(r.get(metric_key)) is not None
                   and safe_int(r.get("p")) is not None]

        by_shape = defaultdict(dict)
        for r in subrows:
            by_shape[r["shape_type"]][safe_int(r["p"])] = safe_float(r[metric_key])

        fig, ax = plt.subplots(figsize=(9, 5))
        label = impl.replace("Implementation ", "Impl ")
        fig.suptitle(title_text + "  |  " + label, fontsize=13)

        for shape, p_dict in sorted(by_shape.items()):
            p_sorted = sorted(p_dict.keys())
            ys = [p_dict[p] for p in p_sorted]
            ax.plot(p_sorted, ys, marker="o", linewidth=1.8,
                    label=shape, color=SHAPE_COLORS.get(shape, "#999"))

        if baseline is not None:
            ax.axhline(baseline, color="#374151", linewidth=1, linestyle="--", label="Baseline")
        ax.set_xlabel("P (number of processes)")
        ax.set_ylabel(y_label)
        ax.set_xticks(sorted(set(safe_int(r["p"]) for r in subrows if safe_int(r["p"]))))
        ax.legend(fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4)
        plt.tight_layout()
        impl_tag = "1d" if "1D" in impl else "2d"
        save(fig, filename_prefix + "_" + impl_tag)


def plot_p_vs_speedup(rows):
    plot_p_vs_metric(
        rows,
        metric_key="aggregate_speedup",
        title_text="P vs Aggregate Speedup by Shape  |  baseline=P=1",
        y_label="Aggregate Speedup over P=1",
        filename_prefix="p_vs_speedup",
        baseline=1.0,
    )


def plot_p_vs_runtime(rows):
    plot_p_vs_metric(
        rows,
        metric_key="avg_seconds",
        title_text="P vs Avg Runtime by Shape",
        y_label="Avg Runtime (seconds)",
        filename_prefix="p_vs_runtime",
    )


def plot_p_vs_cost(rows):
    plot_p_vs_metric(
        rows,
        metric_key="avg_cost",
        title_text="P vs Avg Cost by Shape",
        y_label="Avg Cost (P x seconds)",
        filename_prefix="p_vs_cost",
    )


def plot_p_vs_normalized_runtime(rows):
    plot_p_vs_metric(
        rows,
        metric_key="seconds_per_gop",
        title_text="P vs Normalized Runtime by Shape",
        y_label="Seconds per GOp",
        filename_prefix="p_vs_normalized_runtime",
    )


# ── main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not ANALYSIS_CSV.exists():
        print("Error: " + str(ANALYSIS_CSV) + " not found.")
        print("Run analyze_results.py first to generate it.")
        raise SystemExit(1)
    if not COMBINED_CSV.exists():
        print("Error: " + str(COMBINED_CSV) + " not found.")
        print("Run csv_merger.py first to generate it.")
        raise SystemExit(1)

    print("Loading " + str(ANALYSIS_CSV) + "...")
    analysis_rows = load_csv(ANALYSIS_CSV)
    print("Loaded " + str(len(analysis_rows)) + " rows")

    print("Loading " + str(COMBINED_CSV) + "...")
    combined_rows = load_csv(COMBINED_CSV)
    print("Loaded " + str(len(combined_rows)) + " rows")

    bucket_rows = build_shape_bucket_stats(combined_rows)
    print("Built " + str(len(bucket_rows)) + " aggregated shape buckets")
    summarize_failures(combined_rows)
    report_suspicious_scaling(combined_rows)
    report_shape_rankings(bucket_rows)

    print("\nGenerating graphs in " + str(GRAPH_DIR) + "/")
    print("─" * 50)

    plot_ops_vs_seconds(analysis_rows)
    plot_ops_vs_normalized_runtime(analysis_rows)
    plot_speedup_by_shape(bucket_rows)
    plot_cost_scatter(analysis_rows)
    plot_speedup_heatmap(analysis_rows)
    plot_p_vs_speedup(bucket_rows)
    plot_p_vs_runtime(bucket_rows)
    plot_p_vs_cost(bucket_rows)
    plot_p_vs_normalized_runtime(bucket_rows)

    print("─" * 50)
    print("Done. All graphs saved to " + str(GRAPH_DIR) + "/")
