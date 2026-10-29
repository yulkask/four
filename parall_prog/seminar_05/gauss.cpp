// Семинар 5. Решение СЛАУ методом Гаусса: последовательный и параллельный (OpenMP)
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include <omp.h>

// Прямой ход, k = 0..n-2, i = k+1..n-1:
//   (1) l_ik = a_ik / a_kk
//   (2) a_ij = a_ij - l_ik * a_kj,  j = k..n-1
//   (3) b_i  = b_i  - l_ik * b_k
// Обратный ход, k = n-1..0:
//   (4) x_k = (b_k - sum_{i>k} a_ki * x_i) / a_kk

bool gauss_serial(double* a, double* b, double* x, int n) {
    for (int k = 0; k < n - 1; k++) {
        double pivot = a[k * n + k];
        if (fabs(pivot) < 1e-12) return false;
        for (int i = k + 1; i < n; i++) {
            double lik = a[i * n + k] / pivot;
            for (int j = k; j < n; j++)
                a[i * n + j] -= lik * a[k * n + j];
            b[i] -= lik * b[k];
        }
    }
    if (fabs(a[(n - 1) * n + n - 1]) < 1e-12) return false;

    for (int k = n - 1; k >= 0; k--) {
        x[k] = b[k];
        for (int i = k + 1; i < n; i++)
            x[k] -= a[k * n + i] * x[i];
        x[k] /= a[k * n + k];
    }
    return true;
}

bool gauss_omp(double* a, double* b, double* x, int n) {
    // Ведущие элементы проверяем заранее не можем (они меняются по ходу),
    // поэтому флаг выставляется внутри и все потоки читают его после барьера
    bool ok = true;
#pragma omp parallel
    {
        // Прямой ход: на шаге k строки k+1..n-1 обновляются независимо
        for (int k = 0; k < n - 1; k++) {
            double pivot = a[k * n + k];
            if (fabs(pivot) < 1e-12) {
                ok = false;
                break;
            }
#pragma omp for schedule(dynamic, 16)
            for (int i = k + 1; i < n; i++) {
                double lik = a[i * n + k] / pivot;
                for (int j = k; j < n; j++)
                    a[i * n + j] -= lik * a[k * n + j];
                b[i] -= lik * b[k];
            } // неявный барьер: строка k+1 готова к следующему шагу
        }

        if (ok && fabs(a[(n - 1) * n + n - 1]) < 1e-12) ok = false;

        // Обратный ход O(n^2) выполняет один поток. Вариант из лекции
        // (omp for reduction по i для каждого k) даёт 3 барьера на каждое
        // неизвестное при O(n) работы между ними и оказался медленнее
        // последовательного: n = 1000, 8 потоков — 79 мс против 0.3 мс.
        if (ok) {
#pragma omp single
            for (int k = n - 1; k >= 0; k--) {
                double s = b[k];
                for (int i = k + 1; i < n; i++)
                    s -= a[k * n + i] * x[i];
                x[k] = s / a[k * n + k];
            }
        }
    }
    return ok;
}

double residual(const double* a, const double* b, const double* x, int n) {
    double m = 0.0;
    for (int i = 0; i < n; i++) {
        double s = -b[i];
        for (int j = 0; j < n; j++) s += a[i * n + j] * x[j];
        if (fabs(s) > m) m = fabs(s);
    }
    return m;
}

void print_roots(const char* label, const double* x, int n) {
    printf("  %-14s (", label);
    for (int i = 0; i < n; i++) printf("%s%g", i ? "; " : "", fabs(x[i]) < 1e-9 ? 0.0 : x[i]);
    printf(")\n");
}

// Матричный ввод: имя системы, порядок n, затем n строк расширенной матрицы [A | b]
void solve_file(const char* path) {
    FILE* f = fopen(path, "r");
    if (!f) {
        printf("Не удалось открыть %s\n", path);
        return;
    }
    char name[32];
    int n;
    while (fscanf(f, "%31s %d", name, &n) == 2) {
        double* a = (double*)malloc((size_t)n * n * sizeof(double));
        double* b = (double*)malloc(n * sizeof(double));
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) fscanf(f, "%lf", &a[i * n + j]);
            fscanf(f, "%lf", &b[i]);
        }

        printf("Система %s)\n", name);
        for (int i = 0; i < n; i++) {
            printf("  ");
            for (int j = 0; j < n; j++) printf("%8g ", a[i * n + j]);
            printf("| %8g\n", b[i]);
        }

        double* a1 = (double*)malloc((size_t)n * n * sizeof(double));
        double* b1 = (double*)malloc(n * sizeof(double));
        double* x = (double*)malloc(n * sizeof(double));

        memcpy(a1, a, (size_t)n * n * sizeof(double));
        memcpy(b1, b, n * sizeof(double));
        if (gauss_serial(a1, b1, x, n)) print_roots("последоват.:", x, n);
        else printf("  нулевой ведущий элемент\n");

        memcpy(a1, a, (size_t)n * n * sizeof(double));
        memcpy(b1, b, n * sizeof(double));
        if (gauss_omp(a1, b1, x, n)) {
            print_roots("параллельный:", x, n);
            printf("  max|A*x - b| = %.3e\n\n", residual(a, b, x, n));
        }

        free(a);
        free(b);
        free(a1);
        free(b1);
        free(x);
    }
    fclose(f);
}

// Коэффициенты 1..100 как в лекции. Seed один на всю матрицу: на macOS
// первое значение rand() после srand(i * (n + 1)) почти линейно зависит
// от seed, строки получаются почти одинаковыми и матрица вырождается.
// Диагональное преобладание делает метод без выбора ведущего элемента устойчивым.
void init_random(double* a, double* b, int n) {
    srand(42);
    for (int i = 0; i < n; i++) {
        double row = 0.0;
        for (int j = 0; j < n; j++) {
            a[i * n + j] = rand() % 100 + 1;
            row += a[i * n + j];
        }
        a[i * n + i] = row;
        b[i] = rand() % 100 + 1;
    }
}

void benchmark() {
    int sizes[] = {1000, 2000, 4000};
    int n_sizes = 3;
    int threads[] = {1, 2, 4, 8};
    int n_threads = 4;

    omp_set_dynamic(0);
    FILE* csv = fopen("results/seminar5_gauss.csv", "w");
    if (csv) fprintf(csv, "n,version,threads,time_sec\n");
    printf("n,version,threads,time_sec,residual\n");

    for (int s = 0; s < n_sizes; s++) {
        int n = sizes[s];
        int repeats = (n >= 4000) ? 1 : 3;
        double* a0 = (double*)malloc((size_t)n * n * sizeof(double));
        double* b0 = (double*)malloc(n * sizeof(double));
        double* a = (double*)malloc((size_t)n * n * sizeof(double));
        double* b = (double*)malloc(n * sizeof(double));
        double* x = (double*)malloc(n * sizeof(double));
        init_random(a0, b0, n);

        double best = 1e100;
        for (int r = 0; r < repeats; r++) {
            memcpy(a, a0, (size_t)n * n * sizeof(double));
            memcpy(b, b0, n * sizeof(double));
            double t = omp_get_wtime();
            gauss_serial(a, b, x, n);
            t = omp_get_wtime() - t;
            if (t < best) best = t;
        }
        printf("%d,serial,1,%.6f,%.3e\n", n, best, residual(a0, b0, x, n));
        if (csv) fprintf(csv, "%d,serial,1,%.8f\n", n, best);
        fflush(stdout);

        for (int t = 0; t < n_threads; t++) {
            omp_set_num_threads(threads[t]);
            best = 1e100;
            for (int r = 0; r < repeats; r++) {
                memcpy(a, a0, (size_t)n * n * sizeof(double));
                memcpy(b, b0, n * sizeof(double));
                double tm = omp_get_wtime();
                gauss_omp(a, b, x, n);
                tm = omp_get_wtime() - tm;
                if (tm < best) best = tm;
            }
            printf("%d,omp,%d,%.6f,%.3e\n", n, threads[t], best, residual(a0, b0, x, n));
            if (csv) fprintf(csv, "%d,omp,%d,%.8f\n", n, threads[t], best);
            fflush(stdout);
        }

        free(a0);
        free(b0);
        free(a);
        free(b);
        free(x);
    }
    if (csv) fclose(csv);
}

int main(int argc, char* argv[]) {
    solve_file(argc > 1 ? argv[1] : "seminar_05/systems.txt");
    benchmark();
    return 0;
}
