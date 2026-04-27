import csv
import os
import math
from pathlib import Path

CSV_DIR = Path("./csvs")
OUTPUT_PATH = Path("./csvs/combined_results.csv")
ANALYSIS_PATH = Path("./csvs/shape_analysis.csv")

FIELDNAMES = [
    "implementation", "m", "n", "q", "p",
    "seconds", "speedup", "serial_speedup", "cost", "exit_code", "status",
    "command", "raw_output",
    # derived shape fields
    "a_size", "b_size", "c_size", "total_ops",
    "m_dominant", "n_dominant", "q_dominant", "shape_type"
]

def classify_shape(m, n, q):
    """Classify the shape relationship of the matrices."""
    vals = {"m": m, "n": n, "q": q}
    dominant = max(vals, key=vals.get)
    
    if m == n == q:
        shape_type = "uniform"
    elif n > m and n > q:
        shape_type = "n_dominant"   # wide inner dimension, expensive reduce
    elif m > n and m > q:
        shape_type = "m_dominant"   # tall A matrix
    elif q > m and q > n:
        shape_type = "q_dominant"   # wide C matrix
    elif m == q and n < m:
        shape_type = "square_outer" # square output, small inner
    elif m == q and n > m:
        shape_type = "square_outer_large_n"
    else:
        shape_type = "mixed"

    return dominant, shape_type

def load_csvs():
    rows = []
    files_found = 0
    files_skipped = 0

    for csv_file in sorted(CSV_DIR.glob("*.csv")):
        if csv_file.name == OUTPUT_PATH.name or csv_file.name == ANALYSIS_PATH.name:
            continue

        files_found += 1
        try:
            with open(csv_file, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append((csv_file.name, row))
        except Exception as e:
            print("Skipping " + str(csv_file.name) + ": " + str(e))
            files_skipped += 1

    print("Found " + str(files_found) + " CSV files, skipped " + str(files_skipped))
    print("Total rows loaded: " + str(len(rows)))
    return rows

def enrich_row(row):
    """Add derived shape analysis columns to a row."""
    try:
        m = int(row["m"])
        n = int(row["n"])
        q = int(row["q"])
    except (ValueError, KeyError):
        row["a_size"] = ""
        row["b_size"] = ""
        row["c_size"] = ""
        row["total_ops"] = ""
        row["m_dominant"] = ""
        row["n_dominant"] = ""
        row["q_dominant"] = ""
        row["shape_type"] = "unknown"
        return row

    a_size = m * n
    b_size = n * q
    c_size = m * q
    total_ops = 2 * m * n * q  # multiply-add pairs

    dominant, shape_type = classify_shape(m, n, q)

    row["a_size"] = str(a_size)
    row["b_size"] = str(b_size)
    row["c_size"] = str(c_size)
    row["total_ops"] = str(total_ops)
    row["m_dominant"] = "1" if dominant == "m" else "0"
    row["n_dominant"] = "1" if dominant == "n" else "0"
    row["q_dominant"] = "1" if dominant == "q" else "0"
    row["shape_type"] = shape_type

    return row


def build_baseline_lookups(rows):
    serial_impl = "Implementation 1 (Serial)"
    serial_lookup = {}
    p1_lookup = {}

    for _filename, row in rows:
        if row.get("status", "").strip('"') != "ok":
            continue

        try:
            impl = row["implementation"].strip('"')
            m = int(row["m"])
            n = int(row["n"])
            q = int(row["q"])
            p = int(row["p"])
            seconds = float(row["seconds"])
        except (ValueError, KeyError):
            continue

        if impl == serial_impl:
            serial_lookup[(m, n, q)] = seconds
        elif p == 1:
            p1_lookup[(impl, m, n, q)] = seconds

    return serial_lookup, p1_lookup


def recompute_metrics(row, serial_lookup, p1_lookup):
    row = dict(row)

    try:
        impl = row["implementation"].strip('"')
        m = int(row["m"])
        n = int(row["n"])
        q = int(row["q"])
        p = int(row["p"])
        seconds = float(row["seconds"])
    except (ValueError, KeyError):
        return row

    if row.get("status", "").strip('"') != "ok":
        row["speedup"] = ""
        row["serial_speedup"] = ""
        row["cost"] = ""
        return row

    serial_impl = "Implementation 1 (Serial)"
    row["cost"] = "{:.6f}".format(seconds if impl == serial_impl else p * seconds)

    if impl == serial_impl:
        row["speedup"] = "{:.6f}".format(1.0)
        row["serial_speedup"] = "{:.6f}".format(1.0)
        return row

    p1_seconds = p1_lookup.get((impl, m, n, q))
    serial_seconds = serial_lookup.get((m, n, q))

    row["speedup"] = (
        "{:.6f}".format(p1_seconds / seconds)
        if p1_seconds is not None and seconds > 0.0
        else ""
    )
    row["serial_speedup"] = (
        "{:.6f}".format(serial_seconds / seconds)
        if serial_seconds is not None and seconds > 0.0
        else ""
    )
    return row

def write_combined(rows):
    serial_lookup, p1_lookup = build_baseline_lookups(rows)
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for _filename, row in rows:
            enriched = enrich_row(recompute_metrics(row, serial_lookup, p1_lookup))
            writer.writerow(enriched)
    print("Combined CSV written to: " + str(OUTPUT_PATH))

def write_shape_analysis(rows):
    """
    Aggregate rows by (implementation, shape_type, p) and compute
    average seconds, average speedup, average serial-relative speedup,
    and average cost across all matching runs.
    Only includes rows with status == ok.
    """
    # group by (implementation, shape_type, m, n, q, p)
    serial_lookup, p1_lookup = build_baseline_lookups(rows)
    groups = {}
    for _filename, row in rows:
        row = recompute_metrics(row, serial_lookup, p1_lookup)
        if row.get("status", "").strip('"') != "ok":
            continue
        try:
            seconds = float(row["seconds"])
            p = int(row["p"])
            m = int(row["m"])
            n = int(row["n"])
            q = int(row["q"])
        except (ValueError, KeyError):
            continue

        impl = row["implementation"].strip('"')
        _, shape_type = classify_shape(m, n, q)
        total_ops = 2 * m * n * q

        speedup_str = row.get("speedup", "").strip()
        serial_speedup_str = row.get("serial_speedup", "").strip()
        cost_str = row.get("cost", "").strip()
        speedup = float(speedup_str) if speedup_str and speedup_str != "-" else None
        serial_speedup = (
            float(serial_speedup_str)
            if serial_speedup_str and serial_speedup_str != "-"
            else None
        )
        cost = float(cost_str) if cost_str and cost_str != "-" else None

        key = (impl, shape_type, m, n, q, p, total_ops)
        if key not in groups:
            groups[key] = {"seconds": [], "speedup": [], "serial_speedup": [], "cost": []}

        groups[key]["seconds"].append(seconds)
        if speedup is not None:
            groups[key]["speedup"].append(speedup)
        if serial_speedup is not None:
            groups[key]["serial_speedup"].append(serial_speedup)
        if cost is not None:
            groups[key]["cost"].append(cost)

    analysis_fields = [
        "implementation", "shape_type", "m", "n", "q", "p", "total_ops",
        "avg_seconds", "avg_speedup", "avg_serial_speedup", "avg_cost", "sample_count"
    ]

    with open(ANALYSIS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=analysis_fields)
        writer.writeheader()

        for (impl, shape_type, m, n, q, p, total_ops), data in sorted(groups.items()):
            seconds_list = data["seconds"]
            speedup_list = data["speedup"]
            serial_speedup_list = data["serial_speedup"]
            cost_list = data["cost"]

            avg_seconds = sum(seconds_list) / len(seconds_list)
            avg_speedup = sum(speedup_list) / len(speedup_list) if speedup_list else ""
            avg_serial_speedup = (
                sum(serial_speedup_list) / len(serial_speedup_list)
                if serial_speedup_list else ""
            )
            avg_cost = sum(cost_list) / len(cost_list) if cost_list else ""

            writer.writerow({
                "implementation": impl,
                "shape_type": shape_type,
                "m": m,
                "n": n,
                "q": q,
                "p": p,
                "total_ops": total_ops,
                "avg_seconds": "{:.9f}".format(avg_seconds),
                "avg_speedup": "{:.6f}".format(avg_speedup) if avg_speedup != "" else "",
                "avg_serial_speedup": (
                    "{:.6f}".format(avg_serial_speedup)
                    if avg_serial_speedup != ""
                    else ""
                ),
                "avg_cost": "{:.9f}".format(avg_cost) if avg_cost != "" else "",
                "sample_count": len(seconds_list)
            })

    print("Shape analysis CSV written to: " + str(ANALYSIS_PATH))

def print_summary(rows):
    """Print a quick summary to stdout."""
    ok_rows = [r for _, r in rows if r.get("status", "").strip('"') == "ok"]
    failed_rows = [r for _, r in rows if r.get("status", "").strip('"') != "ok"]

    impls = set(r["implementation"].strip('"') for _, r in rows)
    shapes = set()
    for _, r in rows:
        try:
            _, shape_type = classify_shape(int(r["m"]), int(r["n"]), int(r["q"]))
            shapes.add(shape_type)
        except (ValueError, KeyError):
            pass

    print("")
    print("=== Summary ===")
    print("Total rows:   " + str(len(rows)))
    print("OK rows:      " + str(len(ok_rows)))
    print("Failed rows:  " + str(len(failed_rows)))
    print("Implementations found:")
    for impl in sorted(impls):
        print("  - " + impl)
    print("Shape types found:")
    for shape in sorted(shapes):
        print("  - " + shape)

if __name__ == "__main__":
    if not CSV_DIR.exists():
        print("Error: ./csvs directory not found")
        raise SystemExit(1)

    rows = load_csvs()
    if not rows:
        print("No CSV files found in " + str(CSV_DIR))
        raise SystemExit(1)

    write_combined(rows)
    write_shape_analysis(rows)
    print_summary(rows)
