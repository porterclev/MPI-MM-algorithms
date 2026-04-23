import subprocess
from pathlib import Path

if __name__ == "__main__":
    SCRIPT_DIR = Path(__file__).resolve().parent
    BUILD_SCRIPT = SCRIPT_DIR / "build_all.sh"
    SVG_DIR = SCRIPT_DIR / "graphs"
    CSV_DIR = SCRIPT_DIR / "csvs"
    EXP_DIR = SCRIPT_DIR / "bin" / "group_assignment"
    LOG_DIR = SCRIPT_DIR / "slurm_logs"

    SVG_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.run(["bash", str(BUILD_SCRIPT)], check=True)
    print("=============Finished Building=============")

    scaler = 1
    M = list(range(5 * scaler, 10 * scaler, 1 * scaler))
    N = list(range(5 * scaler, 10 * scaler, 1 * scaler))
    Q = list(range(5 * scaler, 10 * scaler, 1 * scaler))
    P = "1,4,9"
    MAX_P = max(int(p) for p in P.split(","))  # Slurm needs to know the max tasks to allocate

    for m in M:
        for n in N:
            for q in Q:
                job_name = f"matmul_{m}_{n}_{q}"  # concise, unique per actual job
                out_file = LOG_DIR / f"{job_name}_%j.out"
                script_path = LOG_DIR / f"{job_name}.sh"

                sbatch_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks={MAX_P}
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output={out_file}

srun {EXP_DIR} {m} {n} {q} --p={P} \\
     --csv={CSV_DIR}/{job_name}.csv \\
     --svg={SVG_DIR}/{job_name}.svg
"""
                script_path.write_text(sbatch_script)

                result = subprocess.run(
                    ["sbatch", str(script_path)],
                    capture_output=True, text=True
                )
                print(f"Submitted {job_name}: {result.stdout.strip()}")
                if result.returncode != 0:
                    print(f"  ERROR: {result.stderr.strip()}")
