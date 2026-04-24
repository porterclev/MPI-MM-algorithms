#!/bin/bash
#SBATCH --job-name=matmul_6_12_12
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks=9
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=/home/pbclevidence/MPI-MM-algorithms/slurm_logs/matmul_6_12_12_%j.out

module load openmpi/3.1.6
export PATH=/apps/openmpi3/bin:$PATH
export LD_LIBRARY_PATH=/apps/openmpi3/lib:$LD_LIBRARY_PATH
cd /home/pbclevidence/MPI-MM-algorithms

srun /home/pbclevidence/MPI-MM-algorithms/bin/group_assignment 6 12 12 --p=1,4,9 --csv=/home/pbclevidence/MPI-MM-algorithms/csvs/M6_N12_Q12.csv --svg=/home/pbclevidence/MPI-MM-algorithms/graphs/M6_N12_Q12.svg
