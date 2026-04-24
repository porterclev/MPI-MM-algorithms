#include <mpi.h>
#include <cmath>
#include <iostream>
#include <cstdlib>
#include <vector>
using namespace std;

struct Range {
    int begin, end;
};

Range block_rows(int rank, int size, int m) {
    int base = m / size;
    int extra = m % size;
    int begin = rank * base + min(rank, extra);
    int count = base + (rank < extra ? 1 : 0);
    return {begin, begin + count};
}

vector<double> make_matrix(int rows, int cols, int salt) {
    vector<double> M(rows * cols);
    for (int i = 0; i < rows; i++)
        for (int j = 0; j < cols; j++)
            M[i * cols + j] = (i + j + salt) % 10;
    return M;
}

void serial_mm(const vector<double>& A, const vector<double>& B, vector<double>& C,
               int m, int n, int q) {
    fill(C.begin(), C.end(), 0.0);
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < q; j++) {
            double sum = 0.0;
            for (int k = 0; k < n; k++)
                sum += A[i * n + k] * B[k * q + j];
            C[i * q + j] = sum;
        }
    }
}

bool almost_equal(const vector<double>& X, const vector<double>& Y, double eps = 1e-9) {
    if (X.size() != Y.size()) {
        return false;
    }
    for (size_t i = 0; i < X.size(); i++) {
        if (fabs(X[i] - Y[i]) > eps) {
            return false;
        }
    }
    return true;
}

void local_mm(const vector<double>& A, const vector<double>& B, vector<double>& C,
              int local_rows, int n, int q) {
    for (int i = 0; i < local_rows; i++) {
        for (int j = 0; j < q; j++) {
            double sum = 0;
            for (int k = 0; k < n; k++)
                sum += A[i * n + k] * B[k * q + j];
            C[i * q + j] = sum;
        }
    }
}

int main(int argc, char* argv[]) {
    MPI_Init(&argc, &argv);

    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    int m = 8, n = 8, q = 8;
    if (argc == 4) {
        m = atoi(argv[1]);
        n = atoi(argv[2]);
        q = atoi(argv[3]);
    }

    double total_start = MPI_Wtime();
    int dimensions[3] = {m, n, q};
    if (rank == 0) {
        for (int p = 1; p < size; p++)
            MPI_Send(dimensions, 3, MPI_INT, p, 0, MPI_COMM_WORLD);
    } else {
        MPI_Recv(dimensions, 3, MPI_INT, 0, 0, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        m = dimensions[0]; n = dimensions[1]; q = dimensions[2];
    }

    Range r = block_rows(rank, size, m);
    int local_rows = r.end - r.begin;

    vector<double> A_local(local_rows * n);
    vector<double> B(n * q);
    vector<double> C_local(local_rows * q, 0.0);
    vector<double> A, C, C_serial;

    if (rank == 0) {
        A = make_matrix(m, n, 1);
        B = make_matrix(n, q, 2);
        C.resize(m * q);
        C_serial.resize(m * q);

        for (int p = 1; p < size; p++) {
            Range pr = block_rows(p, size, m);
            int rows = pr.end - pr.begin;

            MPI_Send(&rows, 1, MPI_INT, p, 1, MPI_COMM_WORLD);
            MPI_Send(A.data() + pr.begin * n, rows * n, MPI_DOUBLE, p, 2, MPI_COMM_WORLD);
            MPI_Send(B.data(), n * q, MPI_DOUBLE, p, 3, MPI_COMM_WORLD);
        }

        for (int i = 0; i < local_rows * n; i++)
            A_local[i] = A[r.begin * n + i];
    } else {
        int rows;
        MPI_Recv(&rows, 1, MPI_INT, 0, 1, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        MPI_Recv(A_local.data(), rows * n, MPI_DOUBLE, 0, 2, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        MPI_Recv(B.data(), n * q, MPI_DOUBLE, 0, 3, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    }

    double start = MPI_Wtime();
    local_mm(A_local, B, C_local, local_rows, n, q);
    double end = MPI_Wtime();

    if (rank == 0) {
        for (int i = 0; i < local_rows; i++)
            for (int j = 0; j < q; j++)
                C[(r.begin + i) * q + j] = C_local[i * q + j];

        for (int p = 1; p < size; p++) {
            Range pr = block_rows(p, size, m);
            int rows = pr.end - pr.begin;
            MPI_Recv(C.data() + pr.begin * q, rows * q, MPI_DOUBLE, p, 4, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        }

        double total_end = MPI_Wtime();
        double total_time = total_end - total_start;

        serial_mm(A, B, C_serial, m, n, q);

        bool correct = almost_equal(C, C_serial);

        cout << "Local Matrix Multiplication Compute Time: " << (end - start) << " seconds\n";
        cout << "Total Runtime: " << total_time << " seconds\n";
        if (!correct) {
            exit_code = 1;
        }
    } else {
        MPI_Send(C_local.data(), local_rows * q, MPI_DOUBLE, 0, 4, MPI_COMM_WORLD);
    }

    MPI_Finalize();
    return 0;
}