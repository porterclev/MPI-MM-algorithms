#!/bin/bash
#SBATCH --job-name=matmul_5_5_5
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=9
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=/home/porterclev/repos/51,4,9I-55-algorithms/slurm_logs/matmul_5_5_5_%%j.out

srun /home/porterclev/repos/51,4,9I-55-algorithms/bin/group_assignment 5 5 5 --p=1,4,9 --csv=/home/porterclev/repos/MPI-MM-algorithms/csvs/matmul_5_5_5.csv --svg=/home/porterclev/repos/MPI-MM-algorithms/graphs/matmul_5_5_5.svg
