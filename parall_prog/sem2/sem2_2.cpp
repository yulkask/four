// Семинар 2, задание 2. Число Пи (ряд Лейбница) с OpenMP
// Остановка по точности через break, шаг внутреннего цикла = число потоков.
#include <cstdio>
#include <cmath>
#include <omp.h>

int main() {
    const double EPS = 0.0000000001; // 1e-10
    int threads_to_try[] = {1, 2, 4, 8, 16};
    const int n_cases = 5;

    omp_set_dynamic(0);

    FILE* csv = fopen("results/seminar2_pi.csv", "w");
    if (csv) fprintf(csv, "threads,pi,time_sec,terms_approx\n");

    printf("Точность EPS = %.10e\n", EPS);
    printf("threads,pi,time_sec\n");

    for (int c = 0; c < n_cases; c++) {
        int nth = threads_to_try[c];
        omp_set_num_threads(nth);

        double pi = 0.0;
        double start = omp_get_wtime();

        // Внешний цикл по потокам распараллеливаем,
        // внутренний идёт с шагом nthreads до достижения точности.
#pragma omp parallel for reduction(+ : pi)
        for (int t = 0; t < nth; t++) {
            double sum = 0.0;
            int nthreads = nth;
            for (long long i = t;; i += nthreads) {
                double term = ((i & 1LL) ? -4.0 : 4.0) / (2.0 * (double)i + 1.0);
                sum += term;
                if (fabs(term) < EPS) {
                    break;
                }
            }
            pi += sum;
        }

        double elapsed = omp_get_wtime() - start;
        printf("%d,%.12f,%.6f\n", nth, pi, elapsed);
        if (csv) fprintf(csv, "%d,%.15f,%.8f,%.0f\n", nth, pi, elapsed, 2.0 / EPS);
    }

    if (csv) fclose(csv);
    return 0;
}
