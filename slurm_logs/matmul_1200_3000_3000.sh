#!/bin/bash
#SBATCH --job-name=matmul_1200_3000_3000
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=25
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --output=/home/pbclevidence/MPI-MM-algorithms/slurm_logs/matmul_1200_3000_3000_%j.out

export PATH=/apps/openmpi3/bin:$PATH
export LD_LIBRARY_PATH=/apps/openmpi3/lib:$LD_LIBRARY_PATH
cd /home/pbclevidence/MPI-MM-algorithms

/home/pbclevidence/MPI-MM-algorithms/bin/group_assignment 1200 3000 3000 --p=1,4,9,16,25 --csv=/home/pbclevidence/MPI-MM-algorithms/csvs/M1200_N3000_Q3000.csv --svg=/home/pbclevidence/MPI-MM-algorithms/graphs/M1200_N3000_Q3000.svg
