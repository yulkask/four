#include <stdio.h>
#include <omp.h>

#define N 110000000

double a[N + 1], b[N + 1];

int main()
{
    for (int i = 0; i < N; i++) {
        a[i] = 1.034;
        b[i] = 1.057;
    }

    // последовательно
    double seqSum = 0;
    double t0 = omp_get_wtime();
    for (int i = 0; i < N; i++)
        seqSum += a[i] * b[i];
    double seqTime = omp_get_wtime() - t0;

    printf("%-10s %-12s %-10s %s\n", "Threads", "Time, s", "Speedup", "Sum");
    printf("%-10s %-12.4f %-10.2f %f\n", "seq", seqTime, 1.0, seqSum);

    int counts[] = { 1, 2, 4, 8, 16 };
    for (int k = 0; k < 5; k++) {
        int p = counts[k];
        omp_set_num_threads(p);

        double gDotProduct = 0;
        double t1 = omp_get_wtime();

        // reduction: у каждого потока своя копия gDotProduct,
        // в конце копии складываются — гонки данных нет
#pragma omp parallel for reduction(+:gDotProduct)
        for (int i = 0; i < N; i++)
            gDotProduct += a[i] * b[i];

        double parTime = omp_get_wtime() - t1;
        printf("%-10d %-12.4f %-10.2f %f\n", p, parTime, seqTime / parTime, gDotProduct);
    }
    return 0;
}