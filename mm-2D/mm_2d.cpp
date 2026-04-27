#include <mpi.h>

#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

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

vector<double> make_matrix(int rows, int cols, int salt) {
    vector<double> M(rows * cols);
    for (int i = 0; i < rows; ++i) {
        for (int j = 0; j < cols; ++j) {
            M[i * cols + j] = static_cast<double>((i + j + salt) % 10);
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

    const int a_block_elems = block_rows_A * block_cols_A;
    const int b_block_elems = block_rows_B * block_cols_B;
    const int c_block_elems = block_rows_C * block_cols_C;

    vector<double> localA(a_block_elems, 0.0);
    vector<double> localB(b_block_elems, 0.0);
    vector<double> localC(c_block_elems, 0.0);

    MPI_Comm row_comm;
    MPI_Comm col_comm;
    MPI_Comm_split(MPI_COMM_WORLD, proc_row, proc_col, &row_comm);
    MPI_Comm_split(MPI_COMM_WORLD, proc_col, proc_row, &col_comm);

    if (rank == 0) {
        A = make_matrix(m, n, 1);
        B = make_matrix(n, q, 2);
        C.assign(m * q, 0.0);
        C_serial.assign(m * q, 0.0);
    }

    MPI_Barrier(MPI_COMM_WORLD);
    const double parallel_start = MPI_Wtime();

    if (rank == 0) {
        for (int dest = 0; dest < size; ++dest) {
            const int dest_row = dest / sqrtP;
            const int dest_col = dest % sqrtP;
            vector<double> Ablock = extract_block(
                A, n,
                dest_row * block_rows_A, block_rows_A,
                dest_col * block_cols_A, block_cols_A);
            vector<double> Bblock = extract_block(
                B, q,
                dest_row * block_rows_B, block_rows_B,
                dest_col * block_cols_B, block_cols_B);

            if (dest == 0) {
                localA = Ablock;
                localB = Bblock;
            } else {
                MPI_Send(Ablock.data(), static_cast<int>(Ablock.size()), MPI_DOUBLE,
                         dest, 100, MPI_COMM_WORLD);
                MPI_Send(Bblock.data(), static_cast<int>(Bblock.size()), MPI_DOUBLE,
                         dest, 200, MPI_COMM_WORLD);
            }
        }
    } else {
        MPI_Recv(localA.data(), a_block_elems, MPI_DOUBLE, 0, 100, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        MPI_Recv(localB.data(), b_block_elems, MPI_DOUBLE, 0, 200, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    }

    vector<double> a_panel(a_block_elems, 0.0);
    vector<double> b_panel(b_block_elems, 0.0);

    for (int blk = 0; blk < sqrtP; ++blk) {
        if (proc_col == blk) {
            a_panel = localA;
        }
        MPI_Bcast(a_panel.data(), a_block_elems, MPI_DOUBLE, blk, row_comm);

        if (proc_row == blk) {
            b_panel = localB;
        }
        MPI_Bcast(b_panel.data(), b_block_elems, MPI_DOUBLE, blk, col_comm);

        local_block_multiply_add(a_panel, b_panel, localC,
                                 block_rows_A, block_cols_A, block_cols_B);
    }

    if (rank == 0) {
        place_block(C, q, localC,
                    proc_row * block_rows_C, block_rows_C,
                    proc_col * block_cols_C, block_cols_C);

        for (int src = 1; src < size; ++src) {
            vector<double> recvC(c_block_elems, 0.0);
            MPI_Recv(recvC.data(), static_cast<int>(recvC.size()), MPI_DOUBLE,
                     src, 300, MPI_COMM_WORLD, MPI_STATUS_IGNORE);

            const int src_row = src / sqrtP;
            const int src_col = src % sqrtP;
            place_block(C, q, recvC,
                        src_row * block_rows_C, block_rows_C,
                        src_col * block_cols_C, block_cols_C);
        }
    } else {
        MPI_Send(localC.data(), c_block_elems, MPI_DOUBLE, 0, 300, MPI_COMM_WORLD);
    }

    if (rank == 0) {
        const double parallel_end = MPI_Wtime();
        const double parallel_time = parallel_end - parallel_start;

        serial_mm(A, B, C_serial, m, n, q);
        bool correct = almost_equal(C, C_serial);

        cout << "MM-2D completed" << endl;
        cout << "Processes (P): " << size << endl;
        cout << "Grid size    : " << sqrtP << " x " << sqrtP << endl;
        cout << "Matrix sizes : A(" << m << "x" << n << "), B(" << n << "x" << q << "), C(" << m << "x" << q << ")" << endl;
        cout << std::fixed << std::setprecision(6);
        cout << "Parallel Time: " << parallel_time << " seconds" << endl;
        // cout << "Serial time  : " << serial_time << " seconds" << endl;
        // if (parallel_time > 0.0) {
        //     cout << "Speedup      : " << (serial_time / parallel_time) << endl;
        //     cout << "Cost         : " << (size * parallel_time) << endl;
        // }
        // cout << "Correctness  : " << (correct ? "PASSED" : "FAILED") << endl;

        // if (print_result) {
        //     print_matrix(A, m, n, "A");
        //     print_matrix(B, n, q, "B");
        //     print_matrix(C, m, q, "C_parallel");
        //     print_matrix(C_serial, m, q, "C_serial");
        // }
        if(!correct){
            MPI_Comm_free(&row_comm);
            MPI_Comm_free(&col_comm);
            return 1;
        }
    }

    MPI_Comm_free(&row_comm);
    MPI_Comm_free(&col_comm);
    MPI_Finalize();
    return 0;
}
