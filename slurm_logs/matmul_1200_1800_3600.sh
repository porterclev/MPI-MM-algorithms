#!/bin/bash
#SBATCH --job-name=matmul_1200_1800_3600
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=25
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --output=/home/pbclevidence/MPI-MM-algorithms/slurm_logs/matmul_1200_1800_3600_%j.out

export PATH=/apps/openmpi3/bin:$PATH
export LD_LIBRARY_PATH=/apps/openmpi3/lib:$LD_LIBRARY_PATH
cd /home/pbclevidence/MPI-MM-algorithms

/home/pbclevidence/MPI-MM-algorithms/bin/group_assignment 1200 1800 3600 --p=1,4,9,16,25 --csv=/home/pbclevidence/MPI-MM-algorithms/csvs/M1200_N1800_Q3600.csv --svg=/home/pbclevidence/MPI-MM-algorithms/graphs/M1200_N1800_Q3600.svg
