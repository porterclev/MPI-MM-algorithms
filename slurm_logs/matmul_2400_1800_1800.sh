#!/bin/bash
#SBATCH --job-name=matmul_2400_1800_1800
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=25
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --output=/home/pbclevidence/MPI-MM-algorithms/slurm_logs/matmul_2400_1800_1800_%j.out

export PATH=/apps/openmpi3/bin:$PATH
export LD_LIBRARY_PATH=/apps/openmpi3/lib:$LD_LIBRARY_PATH
cd /home/pbclevidence/MPI-MM-algorithms

/home/pbclevidence/MPI-MM-algorithms/bin/group_assignment 2400 1800 1800 --p=1,4,9,16,25 --csv=/home/pbclevidence/MPI-MM-algorithms/csvs/M2400_N1800_Q1800.csv --svg=/home/pbclevidence/MPI-MM-algorithms/graphs/M2400_N1800_Q1800.svg
