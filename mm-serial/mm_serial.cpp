#include <mpi.h>
#include <iostream>
#include <vector>
#include <cstdlib>
#include <ctime>

void randomFill(std::vector<double>& M, int rows, int cols) {
    for (int i = 0; i < rows * cols; i++) {
        M[i] = static_cast<double>(rand() % 10);
    }
}

void printMatrix(const std::string& name,
                 const std::vector<double>& M,
                 int rows, int cols) {
    std::cout << name << " (" << rows << " x " << cols << "):\n";
    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
            std::cout << M[i * cols + j];
            if (j < cols - 1) std::cout << "\t";
        }
        std::cout << "\n";
    }
    std::cout << "\n";
}

int main(int argc, char* argv[]) {

    MPI_Init(&argc, &argv);

    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    if (rank == 0) {

        int m, n, q;

        if (argc == 4) {
            m = std::atoi(argv[1]);
            n = std::atoi(argv[2]);
            q = std::atoi(argv[3]);
        } else {
            m = 4;
            n = 4;
            q = 4;
        }

        std::cout << "MM-ser: Serial Matrix Multiplication\n";
        std::cout << "A(" << m << " x " << n << ") * B("
                  << n << " x " << q << ") = C("
                  << m << " x " << q << ")\n\n";

        std::vector<double> A(m * n, 0.0);
        std::vector<double> B(n * q, 0.0);
        std::vector<double> C(m * q, 0.0);

        srand(static_cast<unsigned int>(time(nullptr)));
        randomFill(A, m, n);
        randomFill(B, n, q);

        bool verbose = (m <= 8 && n <= 8 && q <= 8);
        if (verbose) {
            printMatrix("A", A, m, n);
            printMatrix("B", B, n, q);
        }

        double t_start = MPI_Wtime();

        for (int i = 0; i < m; i++) {
            for (int j = 0; j < q; j++) {
                double sum = 0.0;
                for (int k = 0; k < n; k++) {
                    sum += A[i * n + k] * B[k * q + j];
                }
                C[i * q + j] = sum;
            }
        }

        double t_end = MPI_Wtime();
        double elapsed = t_end - t_start;

        if (verbose) {
            printMatrix("C = A * B", C, m, q);
        }

        std::cout << "Time: " << elapsed << " seconds\n";
    }

    MPI_Finalize();
    return 0;
}
