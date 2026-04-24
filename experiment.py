import subprocess
from pathlib import Path

if __name__ == "__main__":
    SCRIPT_DIR = Path(__file__).resolve().parent
    BUILD_SCRIPT = SCRIPT_DIR / "scripts/build_all.sh"
    SVG_DIR = SCRIPT_DIR / "graphs"
    CSV_DIR = SCRIPT_DIR / "csvs"
    EXP_DIR = SCRIPT_DIR / "bin" / "group_assignment"
    LOG_DIR = SCRIPT_DIR / "slurm_logs"

    SVG_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.run(["bash", str(BUILD_SCRIPT)], check=True)
    print("=============Finished Building=============")

    scaler = 6
    M = list(range(1 * scaler, 5 * scaler, 1 * scaler))
    N = list(range(1 * scaler, 5 * scaler, 1 * scaler))
    Q = list(range(1 * scaler, 5 * scaler, 1 * scaler))
    P = "1, 4"
    MAX_P = max(int(x) for x in P.split(","))

    for m in M:
        for n in N:
            for q in Q:
                job_name  = "matmul_{}_{}_{}" .format(m, n, q)
                out_file  = str(LOG_DIR)  + "/" + job_name + "_%j.out"
                csv_path  = str(CSV_DIR)  + "/" + "M{}_N{}_Q{}.csv".format(m, n, q)
                svg_path  = str(SVG_DIR)  + "/" + "M{}_N{}_Q{}.svg".format(m, n, q)
                script_path = LOG_DIR / (job_name + ".sh")

                srun_line = (
                    "srun " + str(EXP_DIR)
                    + " " + str(m)
                    + " " + str(n)
                    + " " + str(q)
                    + " --p=" + P
                    + " --csv=" + csv_path
                    + " --svg=" + svg_path
                )

                lines = [
                    "#!/bin/bash",
                    "#SBATCH --job-name=" + job_name,
                    "#SBATCH --partition=compute",
                    "#SBATCH --nodes=1",
                    "#SBATCH --ntasks=" + str(MAX_P),
                    "#SBATCH --cpus-per-task=1",
                    "#SBATCH --mem=16G",
                    "#SBATCH --time=01:00:00",
                    "#SBATCH --output=" + out_file,
                    "",
                    "module load openmpi/3.1.6",
                    "export PATH=/apps/openmpi3/bin:$PATH",
		            "export LD_LIBRARY_PATH=/apps/openmpi3/lib:$LD_LIBRARY_PATH",
                    "cd " + str(SCRIPT_DIR),
                    "",
                    srun_line,
                ]

                sbatch_script = "\n".join(lines) + "\n"
                script_path.write_text(sbatch_script)
                result = subprocess.run(
                    ["sbatch", str(script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                print("Submitted " + job_name + ": " + result.stdout.strip())
                if result.returncode != 0:
                    print("  ERROR: " + result.stderr.strip())
