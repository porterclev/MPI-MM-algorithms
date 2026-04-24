#!/bin/bash
#SBATCH --job-name=matmul_18_24_18
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/home/pbclevidence/MPI-MM-algorithms/slurm_logs/matmul_18_24_18_%j.out

module load openmpi/3.1.6
export PATH=/apps/openmpi3/bin:$PATH
export LD_LIBRARY_PATH=/apps/openmpi3/lib:$LD_LIBRARY_PATH
cd /home/pbclevidence/MPI-MM-algorithms

srun /home/pbclevidence/MPI-MM-algorithms/bin/group_assignment 18 24 18 --p=1,4 --csv=/home/pbclevidence/MPI-MM-algorithms/csvs/M18_N24_Q18.csv --svg=/home/pbclevidence/MPI-MM-algorithms/graphs/M18_N24_Q18.svg
