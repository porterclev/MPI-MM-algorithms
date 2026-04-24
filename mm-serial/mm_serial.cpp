#include <iostream>
#include <chrono>
#include <random>
#include <vector>

using namespace std;

vector<double> make_matrix(int rows, int cols, int salt) {
    vector<double> M(rows * cols);
    for (int i = 0; i < rows; i++)
        for (int j = 0; j < cols; j++)
            M[i * cols + j] = (i + j + salt) % 10;
    return M;
}

int main(int argc, char *argv[]) {
    int m = std::stoi(argv[1]);
    int n = std::stoi(argv[2]);
    int q = std::stoi(argv[3]);

    vector<double> A = make_matrix(m, n, 1);
    vector<double> B = make_matrix(n, q, 2);
    vector<double> C(m * q, 0.0);

    auto start = chrono::high_resolution_clock::now();

    for (int i = 0; i < m; i++) {
        for (int j = 0; j < q; j++) {
            for (int k = 0; k < n; k++) {
                C[i * q + j] += A[i * n + k] * B[k * q + j];
            }
        }
    }

    auto end = chrono::high_resolution_clock::now();
    double time_taken = chrono::duration<double>(end - start).count();

    cout << "Time: " << std::fixed << time_taken << " seconds" << endl;

    return 0;
}
