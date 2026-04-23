#!/bin/bash
/apps/openmpi3/bin/mpic++ -std=c++11 -fopenmp $PWD/mm-serial/mm_serial.cpp -o ./bin/mm_serial
/apps/openmpi3/bin/mpic++ -std=c++11 -fopenmp $PWD/mm-1D/mpi_mm_1d.cpp -o ./bin/mm_1d
/apps/openmpi3/bin/mpic++ -std=c++11 -fopenmp $PWD/mm-2D/mm_2d.cpp -o ./bin/mm_2d
/apps/openmpi3/bin/mpic++ -std=c++11 -fopenmp $PWD/experiment.cpp -o ./bin/group_assignment
