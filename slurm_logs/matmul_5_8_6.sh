#!/bin/bash
#SBATCH --job-name=matmul_5_8_6
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=9
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=/home/pbclevidence/MPI-MM-algorithms/slurm_logs/matmul_5_8_6_%j.out

module load openmpi/3.1.6
export LD_LIBRARY_PATH=/apps/openmpi3/lib:$LD_LIBRARY_PATH

srun /home/pbclevidence/MPI-MM-algorithms/bin/group_assignment 5 8 6 --p=1,4,9 --csv=/home/pbclevidence/MPI-MM-algorithms/csvs/M5_N8_Q6.csv --svg=/home/pbclevidence/MPI-MM-algorithms/graphs/M5_N8_Q6.svg
