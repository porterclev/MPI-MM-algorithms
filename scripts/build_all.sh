#!/bin/bash
export PATH=/apps/openmpi3/bin:$PATH
export LD_LIBRARY_PATH=/apps/openmpi3/lib:$LD_LIBRARY_PATH

CXX=/apps/openmpi3/bin/mpic++
CXXFLAGS="-std=c++11 -O3 -DNDEBUG -fopenmp"

$CXX $CXXFLAGS $PWD/mm-serial/mm_serial.cpp -o ./bin/mm_serial
$CXX $CXXFLAGS $PWD/mm-1D/mpi_mm_1d.cpp -o ./bin/mm_1d
$CXX $CXXFLAGS $PWD/mm-2D/mm_2d.cpp -o ./bin/mm_2d
$CXX $CXXFLAGS $PWD/experiment.cpp -o ./bin/group_assignment
