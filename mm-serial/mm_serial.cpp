#include <iostream>
#include <vector>
#include <chrono>

using namespace std;

int main(int argc, char *argv[]) {
    int m = std::stoi(argv[1]);
    int n = std::stoi(argv[2]);
    int q = std::stoi(argv[3]);
    
    vector<vector<double>> A(m, vector<double>(n));
    vector<vector<double>> B(n, vector<double>(q));
    vector<vector<double>> C(m, vector<double>(q, 0));

    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            A[i][j] = 1.0;
        }
    }

    for (int i = 0; i < n; i++) {
        for (int j = 0; j < q; j++) {
            B[i][j] = 1.0;
        }
    }

    auto start = chrono::high_resolution_clock::now();

    for (int i = 0; i < m; i++) {
        for (int j = 0; j < q; j++) {
            for (int k = 0; k < n; k++) {
                C[i][j] += A[i][k] * B[k][j];
            }
        }
    }

    auto end = chrono::high_resolution_clock::now();
    double time_taken = chrono::duration<double>(end - start).count();

    cout << "Time: " << std::fixed << time_taken << " seconds" << endl;

    return 0;
}