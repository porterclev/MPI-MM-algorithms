#include <mpi.h>

#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <chrono>

using std::cerr;
using std::cout;
using std::endl;
using std::size_t;
using std::string;
using std::vector;

static inline double &elem(vector<double> &M, int cols, int r, int c) {
    return M[r * cols + c];
}

static inline double elem_const(const vector<double> &M, int cols, int r, int c) {
    return M[r * cols + c];
}

vector<double> make_matrix(int rows, int cols) {
    vector<double> M(rows * cols);
    for (int i = 0; i < rows; ++i) {
        for (int j = 0; j < cols; ++j) {
            M[i * cols + j] = static_cast<double>(((i + 1) * (j + 2)) % 7 + 1);
        }
    }
    return M;
}

void serial_mm(const vector<double> &A, const vector<double> &B, vector<double> &C,
               int m, int n, int q) {
    std::fill(C.begin(), C.end(), 0.0);
    for (int i = 0; i < m; ++i) {
        for (int j = 0; j < q; ++j) {
            double sum = 0.0;
            for (int k = 0; k < n; ++k) {
                sum += elem_const(A, n, i, k) * elem_const(B, q, k, j);
            }
            elem(C, q, i, j) = sum;
        }
    }
}

vector<double> extract_block(const vector<double> &M, int global_cols,
                             int row_start, int row_count,
                             int col_start, int col_count) {
    vector<double> block(row_count * col_count);
    for (int i = 0; i < row_count; ++i) {
        for (int j = 0; j < col_count; ++j) {
            block[i * col_count + j] = M[(row_start + i) * global_cols + (col_start + j)];
        }
    }
    return block;
}

void place_block(vector<double> &M, int global_cols, const vector<double> &block,
                 int row_start, int row_count,
                 int col_start, int col_count) {
    for (int i = 0; i < row_count; ++i) {
        for (int j = 0; j < col_count; ++j) {
            M[(row_start + i) * global_cols + (col_start + j)] = block[i * col_count + j];
        }
    }
}

void local_block_multiply_add(const vector<double> &Ablock,
                              const vector<double> &Bblock,
                              vector<double> &Cblock,
                              int a_rows, int a_cols, int b_cols) {
    for (int i = 0; i < a_rows; ++i) {
        for (int j = 0; j < b_cols; ++j) {
            double sum = 0.0;
            for (int k = 0; k < a_cols; ++k) {
                sum += Ablock[i * a_cols + k] * Bblock[k * b_cols + j];
            }
            Cblock[i * b_cols + j] += sum;
        }
    }
}

bool almost_equal(const vector<double> &X, const vector<double> &Y, double eps = 1e-9) {
    if (X.size() != Y.size()) {
        return false;
    }
    for (size_t i = 0; i < X.size(); ++i) {
        if (std::fabs(X[i] - Y[i]) > eps) {
            return false;
        }
    }
    return true;
}

void print_matrix(const vector<double> &M, int rows, int cols, const string &name) {
    cout << name << " =\n";
    for (int i = 0; i < rows; ++i) {
        for (int j = 0; j < cols; ++j) {
            cout << std::setw(8) << elem_const(M, cols, i, j) << ' ';
        }
        cout << '\n';
    }
}

int main(int argc, char **argv) {
    MPI_Init(&argc, &argv);

    int rank = 0;
    int size = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    int m = 4;
    int n = 4;
    int q = 4;
    bool print_result = false;

    if (argc >= 4) {
        m = std::atoi(argv[1]);
        n = std::atoi(argv[2]);
        q = std::atoi(argv[3]);
    }
    if (argc >= 5) {
        string flag = argv[4];
        if (flag == "print") {
            print_result = true;
        }
    }

    int sqrtP = static_cast<int>(std::sqrt(static_cast<double>(size)));
    bool ok = true;
    string error_msg;

    if (sqrtP * sqrtP != size) {
        ok = false;
        error_msg = "Number of processes P must be a perfect square.";
    } else if (m % sqrtP != 0 || n % sqrtP != 0 || q % sqrtP != 0) {
        ok = false;
        error_msg = "m, n, and q must each be divisible by sqrt(P).";
    }

    if (!ok) {
        if (rank == 0) {
            cerr << "Error: " << error_msg << endl;
            cerr << "Usage: mpirun -np P ./mm_2d m n q [print]" << endl;
        }
        MPI_Finalize();
        return 1;
    }

    const int proc_row = rank / sqrtP;
    const int proc_col = rank % sqrtP;

    const int block_rows_A = m / sqrtP;
    const int block_cols_A = n / sqrtP;
    const int block_rows_B = n / sqrtP;
    const int block_cols_B = q / sqrtP;
    const int block_rows_C = m / sqrtP;
    const int block_cols_C = q / sqrtP;

    vector<double> A;
    vector<double> B;
    vector<double> C;
    vector<double> C_serial;

    if (rank == 0) {
        A = make_matrix(m, n);
        B = make_matrix(n, q);
        C.assign(m * q, 0.0);
        C_serial.assign(m * q, 0.0);
    }

    vector<double> localC(block_rows_C * block_cols_C, 0.0);

    std::chrono::high_resolution_clock::time_point parallel_start;
    if (rank == 0) {
        parallel_start = std::chrono::high_resolution_clock::now();
    }

    if (rank == 0) {
        for (int dest = 0; dest < size; ++dest) {
            int dest_row = dest / sqrtP;
            int dest_col = dest % sqrtP;

            for (int blk = 0; blk < sqrtP; ++blk) {
                vector<double> Ablock = extract_block(
                    A, n,
                    dest_row * block_rows_A, block_rows_A,
                    blk * block_cols_A, block_cols_A);

                vector<double> Bblock = extract_block(
                    B, q,
                    blk * block_rows_B, block_rows_B,
                    dest_col * block_cols_B, block_cols_B);

                if (dest == 0) {
                    local_block_multiply_add(Ablock, Bblock, localC,
                                             block_rows_A, block_cols_A, block_cols_B);
                } else {
                    MPI_Send(Ablock.data(), static_cast<int>(Ablock.size()), MPI_DOUBLE,
                             dest, 100 + blk, MPI_COMM_WORLD);
                    MPI_Send(Bblock.data(), static_cast<int>(Bblock.size()), MPI_DOUBLE,
                             dest, 200 + blk, MPI_COMM_WORLD);
                }
            }
        }

        place_block(C, q, localC,
                    proc_row * block_rows_C, block_rows_C,
                    proc_col * block_cols_C, block_cols_C);

        for (int src = 1; src < size; ++src) {
            vector<double> recvC(block_rows_C * block_cols_C, 0.0);
            MPI_Recv(recvC.data(), static_cast<int>(recvC.size()), MPI_DOUBLE,
                     src, 300, MPI_COMM_WORLD, MPI_STATUS_IGNORE);

            int src_row = src / sqrtP;
            int src_col = src % sqrtP;
            place_block(C, q, recvC,
                        src_row * block_rows_C, block_rows_C,
                        src_col * block_cols_C, block_cols_C);
        }
    } else {
        for (int blk = 0; blk < sqrtP; ++blk) {
            vector<double> Ablock(block_rows_A * block_cols_A, 0.0);
            vector<double> Bblock(block_rows_B * block_cols_B, 0.0);

            MPI_Recv(Ablock.data(), static_cast<int>(Ablock.size()), MPI_DOUBLE,
                     0, 100 + blk, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            MPI_Recv(Bblock.data(), static_cast<int>(Bblock.size()), MPI_DOUBLE,
                     0, 200 + blk, MPI_COMM_WORLD, MPI_STATUS_IGNORE);

            local_block_multiply_add(Ablock, Bblock, localC,
                                     block_rows_A, block_cols_A, block_cols_B);
        }

        MPI_Send(localC.data(), static_cast<int>(localC.size()), MPI_DOUBLE,
                 0, 300, MPI_COMM_WORLD);
    }

    if (rank == 0) {
        auto parallel_end = std::chrono::high_resolution_clock::now();
        double parallel_time = std::chrono::duration<double>(parallel_end - parallel_start).count();

        auto serial_start = std::chrono::high_resolution_clock::now();
        serial_mm(A, B, C_serial, m, n, q);
        auto serial_end = std::chrono::high_resolution_clock::now();
        double serial_time = std::chrono::duration<double>(serial_end - serial_start).count();

        bool correct = almost_equal(C, C_serial);

        cout << "MM-2D completed" << endl;
        cout << "Processes (P): " << size << endl;
        cout << "Grid size    : " << sqrtP << " x " << sqrtP << endl;
        cout << "Matrix sizes : A(" << m << "x" << n << "), B(" << n << "x" << q << "), C(" << m << "x" << q << ")" << endl;
        cout << std::fixed << std::setprecision(6);
        cout << "Parallel time: " << parallel_time << " seconds" << endl;
        cout << "Serial time  : " << serial_time << " seconds" << endl;
        if (parallel_time > 0.0) {
            cout << "Speedup      : " << (serial_time / parallel_time) << endl;
            cout << "Cost         : " << (size * parallel_time) << endl;
        }
        cout << "Correctness  : " << (correct ? "PASSED" : "FAILED") << endl;

        if (print_result) {
            print_matrix(A, m, n, "A");
            print_matrix(B, n, q, "B");
            print_matrix(C, m, q, "C_parallel");
            print_matrix(C_serial, m, q, "C_serial");
        }
    }

    MPI_Finalize();
    return 0;
}
