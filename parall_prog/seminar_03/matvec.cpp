// Семинар 3. Параллельное умножение матрицы на вектор (OpenMP)
// A[i][j] = 1 + (i+j)%7, b[j] = 1. Элементы матрицы считаются по формуле,
// чтобы прогнать все требуемые размеры (до 30000) на 8 ГБ RAM.
#include <cstdio>
#include <cstdlib>
#include <omp.h>

int main() {
    int sizes[] = {5000, 10000, 15000, 20000, 25000, 30000};
    int n_sizes = 6;
    int threads[] = {1, 2, 4, 8};
    int n_threads = 4;
    const int repeats = 3;

    omp_set_dynamic(0);

    FILE* csv = fopen("results/seminar3_matvec.csv", "w");
    if (csv) fprintf(csv, "rows,threads,time_sec,speedup,checksum\n");

    printf("rows,threads,time_sec,speedup,checksum\n");

    for (int s = 0; s < n_sizes; s++) {
        int n = sizes[s];
        double* b = (double*)malloc((size_t)n * sizeof(double));
        double* c = (double*)malloc((size_t)n * sizeof(double));
        if (!b || !c) {
            printf("Недостаточно памяти для векторов n=%d\n", n);
            return 1;
        }
        for (int i = 0; i < n; i++) b[i] = 1.0;

        double t1 = 0.0;
        for (int t = 0; t < n_threads; t++) {
            int nth = threads[t];
            omp_set_num_threads(nth);
            double best = 1e100;

            for (int r = 0; r < repeats; r++) {
                double start = omp_get_wtime();
#pragma omp parallel for schedule(static)
                for (int i = 0; i < n; i++) {
                    double sum = 0.0;
                    for (int j = 0; j < n; j++) {
                        double aij = 1.0 + (double)((i + j) % 7);
                        sum += aij * b[j];
                    }
                    c[i] = sum;
                }
                double elapsed = omp_get_wtime() - start;
                if (elapsed < best) best = elapsed;
            }

            double checksum = 0.0;
            for (int i = 0; i < n; i++) checksum += c[i];
            if (nth == 1) t1 = best;
            double speedup = t1 / best;
            printf("%d,%d,%.6f,%.4f,%.6f\n", n, nth, best, speedup, checksum);
            if (csv) fprintf(csv, "%d,%d,%.8f,%.6f,%.10f\n", n, nth, best, speedup, checksum);
            fflush(stdout);
        }

        free(b);
        free(c);
    }

    if (csv) fclose(csv);
    return 0;
}
