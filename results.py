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


# ── 2. Bar chart: avg speedup by shape_type per implementation ───────────────
def plot_speedup_by_shape(rows):
    targets = ["Implementation 2 (MM-1D)", "Implementation 3 (MM-2D)"]
    p_values = sorted(set(safe_int(r["p"]) for r in rows if safe_int(r["p"]) is not None))

    for p in p_values:
        # collect avg speedup per (impl, shape_type)
        data = defaultdict(dict)
        for r in rows:
            if safe_int(r["p"]) != p:
                continue
            if r["implementation"] not in targets:
                continue
            sp = safe_float(r.get("avg_speedup", ""))
            if sp is None:
                continue
            shape = r["shape_type"]
            key = r["implementation"]
            if shape not in data[key]:
                data[key][shape] = []
            data[key][shape].append(sp)

        # average across dimensions with same shape_type
        averaged = {}
        for impl in targets:
            averaged[impl] = {}
            for shape, vals in data[impl].items():
                averaged[impl][shape] = sum(vals) / len(vals)

        all_shapes = sorted(set(s for d in averaged.values() for s in d))
        if not all_shapes:
            continue

        x = list(range(len(all_shapes)))
        width = 0.35
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.suptitle("Avg Speedup by Shape Type  |  P=" + str(p), fontsize=13)

        for i, impl in enumerate(targets):
            vals = [averaged[impl].get(s, 0.0) for s in all_shapes]
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
        ax.set_ylabel("Avg Speedup over Serial")
        ax.set_xlabel("Shape Type")
        ax.legend(fontsize=9)
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)
        plt.tight_layout()
        save(fig, "speedup_by_shape_p" + str(p))


# ── 3. Scatter: cost vs total_ops colored by shape_type ─────────────────────
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


# ── 4. Heatmap: m vs q, color = speedup (one per impl, per p, fix n) ─────────
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
                "Speedup Heatmap  |  " + label + "  |  P=" + str(p) + "  |  n=" + str(median_n),
                fontsize=12
            )

            cmap = "RdYlGn"
            im = ax.imshow(grid, aspect="auto", cmap=cmap, origin="lower",
                           vmin=0, vmax=max(2.0, float(np.nanmax(grid))))
            plt.colorbar(im, ax=ax, label="Speedup")

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


# ── 5. Line plot: P vs speedup per shape_type ────────────────────────────────
def plot_p_vs_speedup(rows):
    targets = ["Implementation 2 (MM-1D)", "Implementation 3 (MM-2D)"]

    for impl in targets:
        subrows = [r for r in rows
                   if r["implementation"] == impl
                   and safe_float(r.get("avg_speedup")) is not None
                   and safe_int(r.get("p")) is not None]

        by_shape = defaultdict(lambda: defaultdict(list))
        for r in subrows:
            by_shape[r["shape_type"]][safe_int(r["p"])].append(
                safe_float(r["avg_speedup"])
            )

        fig, ax = plt.subplots(figsize=(9, 5))
        label = impl.replace("Implementation ", "Impl ")
        fig.suptitle("P vs Avg Speedup by Shape  |  " + label, fontsize=13)

        for shape, p_dict in sorted(by_shape.items()):
            p_sorted = sorted(p_dict.keys())
            ys = [sum(p_dict[p]) / len(p_dict[p]) for p in p_sorted]
            marker = "o"
            ax.plot(p_sorted, ys, marker=marker, linewidth=1.8,
                    label=shape, color=SHAPE_COLORS.get(shape, "#999"))

        ax.axhline(1.0, color="#374151", linewidth=1, linestyle="--", label="Baseline")
        ax.set_xlabel("P (number of processes)")
        ax.set_ylabel("Avg Speedup over Serial")
        ax.set_xticks(sorted(set(safe_int(r["p"]) for r in subrows if safe_int(r["p"]))))
        ax.legend(fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4)
        plt.tight_layout()
        impl_tag = "1d" if "1D" in impl else "2d"
        save(fig, "p_vs_speedup_" + impl_tag)


# ── main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not ANALYSIS_CSV.exists():
        print("Error: " + str(ANALYSIS_CSV) + " not found.")
        print("Run analyze_results.py first to generate it.")
        raise SystemExit(1)

    print("Loading " + str(ANALYSIS_CSV) + "...")
    rows = load_csv(ANALYSIS_CSV)
    print("Loaded " + str(len(rows)) + " rows")

    print("\nGenerating graphs in " + str(GRAPH_DIR) + "/")
    print("─" * 50)

    plot_ops_vs_seconds(rows)
    plot_speedup_by_shape(rows)
    plot_cost_scatter(rows)
    plot_speedup_heatmap(rows)
    plot_p_vs_speedup(rows)

    print("─" * 50)
    print("Done. All graphs saved to " + str(GRAPH_DIR) + "/")