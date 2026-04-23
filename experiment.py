import subprocess
from pathlib import Path

if __name__ == "__main__":
    SCRIPT_DIR = Path(__file__).resolve().parent
    SOURCE_DIR =  SCRIPT_DIR.parent
    BUILD_DIR = str(SCRIPT_DIR) + "/build_all.sh"
    SVG_DIR = str(SOURCE_DIR) + "/graphs"
    
    subprocess.run(["bash", BUILD_DIR])
    print("=============Finished Building=============")
    M = [1000, 800]
    N = [1000, 800]
    Q = [1000, 800]
    P = "1,4,9,16,25"
    
    
    subprocess.run([
        f"{SOURCE_DIR}/group_assignment",
        str(M[0]),
        str(N[0]),
        str(Q[0]),
        f"--p={P}",
        "--csv=csvs/uniform_shape.csv",
        "--svg=graphs/uniform_shape.svg"
    ])
    
    subprocess.run([
        f"{SOURCE_DIR}/group_assignment",
        str(M[1]),
        str(N[0]),
        str(Q[0]),
        f"--p={P}",
        "--csv=csvs/M_diff.csv",
        "--svg=graphs/M_diff.svg"
    ])
    subprocess.run([
        f"{SOURCE_DIR}/group_assignment",
        str(M[0]),
        str(N[1]),
        str(Q[0]),
        f"--p={P}",
        "--csv=csvs/N_diff.csv",
        "--svg=graphs/N_diff.svg"
    ])
    subprocess.run([
        f"{SOURCE_DIR}/group_assignment",
        str(M[0]),
        str(N[0]),
        str(Q[1]),
        f"--p={P}",
        "--csv=csvs/Q_diff.csv",
        "--svg=graphs/Q_diff.svg"
    ])
    
