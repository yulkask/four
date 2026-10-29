// Семинар 6. LU-разложение и решение СЛАУ с OpenMP
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include <omp.h>

// Шаг 1. Матрица L на основе матрицы A.
// Прямой ход метода Гаусса на копии A: множители l_ik = a_ik / a_kk
// образуют L (единичная диагональ). На шаге k строки i > k обновляются
// независимо друг от друга — этот цикл распараллеливается.
bool compute_L(const double* A, double* L, int n) {
    double* W = (double*)malloc((size_t)n * n * sizeof(double));
    memcpy(W, A, (size_t)n * n * sizeof(double));
    memset(L, 0, (size_t)n * n * sizeof(double));

    for (int k = 0; k < n; k++) L[k * n + k] = 1.0;

    // Параллельная область создаётся один раз; потоки синхронизируются
    // неявным барьером omp for в конце каждого шага k
    bool ok = true;
#pragma omp parallel
    for (int k = 0; k < n; k++) {
        double pivot = W[k * n + k];
        if (fabs(pivot) < 1e-12) {
            ok = false;  // все потоки видят одно и то же значение и выходят вместе
            break;
        }
#pragma omp for schedule(dynamic, 16)
        for (int i = k + 1; i < n; i++) {
            double l = W[i * n + k] / pivot;
            L[i * n + k] = l;
            for (int j = k + 1; j < n; j++) {
                W[i * n + j] -= l * W[k * n + j];
            }
        }
    }
    free(W);
    return ok;
}

// Шаг 2. Матрица U на основе матриц A и L.
// Из A = L*U: u_ij = a_ij - sum_{k<i} l_ik * u_kj, i <= j.
// Каждый столбец U вычисляется независимо от остальных (это прямая
// подстановка L * U[:,j] = A[:,j]), поэтому распараллеливаем по блокам
// столбцов. Внутри блока строка U[i] = A[i] - sum_k l_ik * U[k] обходится
// подряд по памяти.
void compute_U(const double* A, const double* L, double* U, int n) {
    const int block = 64;
    memset(U, 0, (size_t)n * n * sizeof(double));
#pragma omp parallel for schedule(dynamic, 1)
    for (int jj = 0; jj < n; jj += block) {
        int j_max = (jj + block < n) ? jj + block : n;
        for (int i = 0; i < j_max; i++) {
            int j_min = (i > jj) ? i : jj;
            double* u_i = U + (size_t)i * n;
            for (int j = j_min; j < j_max; j++) u_i[j] = A[i * n + j];
            for (int k = 0; k < i; k++) {
                double l_ik = L[i * n + k];
                const double* u_k = U + (size_t)k * n;
                for (int j = j_min; j < j_max; j++) u_i[j] -= l_ik * u_k[j];
            }
        }
    }
}

bool lu_decompose(const double* A, double* L, double* U, int n) {
    if (!compute_L(A, L, n)) return false;
    compute_U(A, L, U, n);
    return true;
}

// L*y = b, затем U*x = y
void lu_solve(const double* L, const double* U, const double* b, double* x, int n) {
    double* y = (double*)malloc(n * sizeof(double));
    for (int i = 0; i < n; i++) {
        double s = b[i];
        for (int k = 0; k < i; k++) s -= L[i * n + k] * y[k];
        y[i] = s;
    }
    for (int i = n - 1; i >= 0; i--) {
        double s = y[i];
        for (int k = i + 1; k < n; k++) s -= U[i * n + k] * x[k];
        x[i] = s / U[i * n + i];
    }
    free(y);
}

void matmul(const double* A, const double* B, double* C, int n) {
#pragma omp parallel for schedule(static)
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) C[i * n + j] = 0.0;
        for (int k = 0; k < n; k++) {
            double a_ik = A[i * n + k];
            for (int j = 0; j < n; j++) C[i * n + j] += a_ik * B[k * n + j];
        }
    }
}

double max_diff(const double* A, const double* B, int n) {
    double m = 0.0;
    for (int i = 0; i < n * n; i++) {
        double d = fabs(A[i] - B[i]);
        if (d > m) m = d;
    }
    return m;
}

double residual(const double* A, const double* x, const double* b, int n) {
    double m = 0.0;
    for (int i = 0; i < n; i++) {
        double s = -b[i];
        for (int j = 0; j < n; j++) s += A[i * n + j] * x[j];
        if (fabs(s) > m) m = fabs(s);
    }
    return m;
}

void print_matrix(const char* name, const double* M, int n) {
    printf("%s =\n", name);
    for (int i = 0; i < n; i++) {
        printf("  ");
        for (int j = 0; j < n; j++) printf("%10.4f ", M[i * n + j]);
        printf("\n");
    }
}

struct System {
    const char* name;
    int n;
    double A[9];
    double b[3];
};

void solve_tasks() {
    // Свободные члены перенесены в правую часть (в: 2x1 + 3x2 + 1 = 0 -> = -1)
    System tasks[] = {
        {"а", 2, {7, -2, 5, 3}, {8, 19}},
        {"б", 2, {3, -4, 2, 5}, {-11, 8}},
        {"в", 2, {2, 3, 3, 4}, {-1, -1}},
        {"г", 3, {1, 3, -1, 2, 4, 3, 3, -2, 5}, {-2, 3, 13}},
        {"д", 3, {2, -1, 1, 3, -2, -3, 1, 1, 1}, {0, 11, 6}},
        {"е", 3, {1, 1, -1, 2, 3, -4, 7, -1, -3}, {6, 21, 6}},
        {"ж", 3, {4, -2, 1, 1, 3, -2, 3, -1, 4}, {6, 5, 5}},
        {"з", 3, {2, -3, 0, 3, 1, -2, 1, -1, 3}, {2, 5, -2}},
        {"и", 3, {3, -1, 2, 1, 3, 0, -1, 2, 3}, {1, -1, 7}},
        {"к", 3, {5732, 2134, 2134, 2134, 5732, 2134, 2134, 2134, 5732}, {7866, 670, 11464}},
    };
    int n_tasks = sizeof(tasks) / sizeof(tasks[0]);

    for (int t = 0; t < n_tasks; t++) {
        System& s = tasks[t];
        int n = s.n;
        double L[9], U[9], LU[9], x[3];

        printf("Система %s)\n", s.name);
        print_matrix("A", s.A, n);
        if (!lu_decompose(s.A, L, U, n)) {
            printf("Нулевой ведущий элемент, LU-разложение без перестановок невозможно\n\n");
            continue;
        }
        print_matrix("L", L, n);
        print_matrix("U", U, n);
        matmul(L, U, LU, n);
        print_matrix("L*U", LU, n);
        printf("max|L*U - A| = %.3e\n", max_diff(LU, s.A, n));

        lu_solve(L, U, s.b, x, n);
        printf("Решение: (");
        for (int i = 0; i < n; i++) printf("%s%g", i ? "; " : "", fabs(x[i]) < 1e-12 ? 0.0 : x[i]);
        printf(")\nmax|A*x - b| = %.3e\n\n", residual(s.A, x, s.b, n));
    }
}

void benchmark() {
    const int N = 1000;
    const int repeats = 3;
    int threads[] = {1, 2, 4, 8};
    int n_threads = 4;

    double* A = (double*)malloc((size_t)N * N * sizeof(double));
    double* L = (double*)malloc((size_t)N * N * sizeof(double));
    double* U = (double*)malloc((size_t)N * N * sizeof(double));
    double* LU = (double*)malloc((size_t)N * N * sizeof(double));
    double* b = (double*)malloc(N * sizeof(double));
    double* x = (double*)malloc(N * sizeof(double));

    // Произвольные коэффициенты; диагональное преобладание гарантирует,
    // что ведущие элементы не обнулятся (разложение без перестановок)
    srand(42);
    for (int i = 0; i < N; i++) {
        double row = 0.0;
        for (int j = 0; j < N; j++) {
            A[i * N + j] = (double)rand() / RAND_MAX * 20.0 - 10.0;
            row += fabs(A[i * N + j]);
        }
        A[i * N + i] = row + 1.0;
        b[i] = (double)rand() / RAND_MAX * 200.0 - 100.0;
    }

    FILE* csv = fopen("results/seminar6_lu.csv", "w");
    if (csv) fprintf(csv, "n,threads,time_sec,speedup,efficiency\n");
    printf("N = %d \n", N);
    printf("threads,time_sec,speedup,efficiency\n");

    omp_set_dynamic(0);
    double t1 = 0.0;
    for (int t = 0; t < n_threads; t++) {
        int nth = threads[t];
        omp_set_num_threads(nth);
        double best = 1e100;
        for (int r = 0; r < repeats; r++) {
            double start = omp_get_wtime();
            lu_decompose(A, L, U, N);
            lu_solve(L, U, b, x, N);
            double elapsed = omp_get_wtime() - start;
            if (elapsed < best) best = elapsed;
        }
        if (nth == 1) t1 = best;
        double speedup = t1 / best;
        double eff = speedup / nth;
        printf("%d,%.6f,%.3f,%.3f\n", nth, best, speedup, eff);
        if (csv) fprintf(csv, "%d,%d,%.8f,%.6f,%.6f\n", N, nth, best, speedup, eff);
        fflush(stdout);
    }
    if (csv) fclose(csv);

    matmul(L, U, LU, N);
    printf("max|L*U - A| = %.3e\n", max_diff(LU, A, N));
    printf("max|A*x - b| = %.3e\n", residual(A, x, b, N));

    free(A);
    free(L);
    free(U);
    free(LU);
    free(b);
    free(x);
}

int main() {
    solve_tasks();
    benchmark();
    return 0;
}
