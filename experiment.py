import subprocess
from pathlib import Path

if __name__ == "__main__":
    SCRIPT_DIR = Path(__file__).resolve().parent  # BUG FIX: .resolve() gives the file, not the dir
    BUILD_SCRIPT = SCRIPT_DIR / "build_all.sh"    # use Path / operator instead of str concatenation
    SVG_DIR = SCRIPT_DIR / "graphs"
    CSV_DIR = SCRIPT_DIR / "csvs"
    EXP_DIR = SCRIPT_DIR / "bin" / "group_assignment"

    # Ensure output directories exist
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.run(["bash", str(BUILD_SCRIPT)], check=True)
    print("=============Finished Building=============")

    scaler = 1
    M = list(range(5 * scaler, 10 * scaler, 1 * scaler))
    N = list(range(5 * scaler, 10 * scaler, 1 * scaler))
    Q = list(range(5 * scaler, 10 * scaler, 1 * scaler))
    P_VALUES = [1, 4, 9]

    for m in M:
        for n in N:
            for q in Q:
                for p in P_VALUES:
                    job_name = f"matmul_m{m}_n{n}_q{q}_p{p}"
                    out_file = SCRIPT_DIR / "slurm_logs" / f"{job_name}_%j.out"
                    out_file.parent.mkdir(parents=True, exist_ok=True)

                    # Write a temporary sbatch script for this job
                    sbatch_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks={p}
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output={out_file}

srun {EXP_DIR} {m} {n} {q} --p={p} \\
     --csv={CSV_DIR}/uniform_shape_m{m}_n{n}_q{q}_p{p}.csv \\
     --svg={SVG_DIR}/uniform_shape_m{m}_n{n}_q{q}_p{p}.svg
"""
                    script_path = SCRIPT_DIR / "slurm_logs" / f"{job_name}.sh"
                    script_path.write_text(sbatch_script)

                    result = subprocess.run(
                        ["sbatch", str(script_path)],
                        capture_output=True, text=True
                    )
                    print(f"Submitted {job_name}: {result.stdout.strip()}")
                    if result.returncode != 0:
                        print(f"  ERROR: {result.stderr.strip()}")
