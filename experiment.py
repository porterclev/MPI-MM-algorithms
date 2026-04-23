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

    template = (
        "#!/bin/bash\n"
        "#SBATCH --job-name=JOB_NAME\n"
        "#SBATCH --partition=compute\n"
        "#SBATCH --nodes=1\n"
        "#SBATCH --ntasks=MAX_P\n"
        "#SBATCH --cpus-per-task=1\n"
        "#SBATCH --mem=4G\n"
        "#SBATCH --time=00:10:00\n"
        "#SBATCH --output=OUT_FILE\n"
        "\n"
        "srun EXP_DIR M N Q --p=P --csv=CSV_DIR/JOB_NAME.csv --svg=SVG_DIR/JOB_NAME.svg\n"
    )
    # subprocess.run(["bash", str(BUILD_SCRIPT)], check=True)
    print("=============Finished Building=============")

    scaler = 1
    M = list(range(5 * scaler, 10 * scaler, 1 * scaler))
    N = list(range(5 * scaler, 10 * scaler, 1 * scaler))
    Q = list(range(5 * scaler, 10 * scaler, 1 * scaler))
    P = "1,4,9"
    MAX_P = max(int(p) for p in P.split(","))

    for m in M:
        for n in N:
            for q in Q:
                job_name = "matmul_{}_{}_{}" .format(m, n, q)
                out_file = LOG_DIR / "{}_%%j.out".format(job_name) 
                script_path = LOG_DIR / "{}.sh".format(job_name)
                csv = CSV_DIR / "M:{}_N:{}_Q:{}.csv".format(m, n, q)
                svg = SVG_DIR / "M:{}_N:{}_Q:{}.svg".format(m, n, q)

                sbatch_script = (
                                    template
                                    .replace("JOB_NAME", job_name)
                                    .replace("MAX_P", str(MAX_P))
                                    .replace("OUT_FILE", str(out_file))
                                    .replace("EXP_DIR", str(EXP_DIR))
                                    .replace("M", str(m))
                                    .replace("N", str(n))
                                    .replace("Q", str(q))
                                    .replace("P", str(P))
                                    .replace("CSV_DIR", str(csv))
                                    .replace("SVG_DIR", str(svg))
                                )
                script_path.write_text(sbatch_script)

                result = subprocess.run(
                    ["sbatch", str(script_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                print(f"Submitted {job_name}: {result.stdout.strip()}")
                if result.returncode != 0:
                    print(f"  ERROR: {result.stderr.strip()}")
