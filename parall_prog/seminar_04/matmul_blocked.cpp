// Семинар 4. Блочное умножение матриц с OpenMP
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <omp.h>

void matrix_mul_blocked_openmp(double* A, double* B, double* C, int N, int block_size) {
#pragma omp parallel for schedule(static)
    for (int ii = 0; ii < N; ii += block_size) {
        for (int jj = 0; jj < N; jj += block_size) {
            for (int kk = 0; kk < N; kk += block_size) {
                int i_max = (ii + block_size < N) ? ii + block_size : N;
                int j_max = (jj + block_size < N) ? jj + block_size : N;
                int k_max = (kk + block_size < N) ? kk + block_size : N;
                for (int i = ii; i < i_max; i++) {
                    for (int k = kk; k < k_max; k++) {
                        double a_ik = A[i * N + k];
                        for (int j = jj; j < j_max; j++) {
                            C[i * N + j] += a_ik * B[k * N + j];
                        }
                    }
                }
            }
        }
    }
}

int main() {
    int sizes[] = {1000, 2000, 4000};
    int n_sizes = 3;
    int threads[] = {2, 4, 8};
    int n_threads = 3;
    // L1 D-cache Apple M2 ≈ 64 КБ → размер блока по формуле ~64
    // Размер 1 < кэш, размер 2 = кэш, размер 3 > кэш
    int blocks[] = {32, 64, 128};
    int n_blocks = 3;
    const int repeats = 2;

    omp_set_dynamic(0);

    FILE* csv = fopen("results/seminar4_matmul.csv", "w");
    if (csv) fprintf(csv, "n,threads,block,time_sec,checksum\n");

    printf("n,threads,block,time_sec,checksum\n");

    for (int s = 0; s < n_sizes; s++) {
        int N = sizes[s];
        double* A = (double*)malloc((size_t)N * N * sizeof(double));
        double* B = (double*)malloc((size_t)N * N * sizeof(double));
        double* C = (double*)malloc((size_t)N * N * sizeof(double));
        if (!A || !B || !C) {
            printf("Недостаточно памяти для N=%d\n", N);
            return 1;
        }

        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                A[i * N + j] = 1.0;
                B[i * N + j] = 1.0;
            }
        }

        for (int t = 0; t < n_threads; t++) {
            int nth = threads[t];
            omp_set_num_threads(nth);
            for (int b = 0; b < n_blocks; b++) {
                int bs = blocks[b];
                double best = 1e100;
                for (int r = 0; r < repeats; r++) {
                    memset(C, 0, (size_t)N * N * sizeof(double));
                    double start = omp_get_wtime();
                    matrix_mul_blocked_openmp(A, B, C, N, bs);
                    double elapsed = omp_get_wtime() - start;
                    if (elapsed < best) best = elapsed;
                }
                double checksum = C[0] + C[N * N / 2] + C[N * N - 1];
                printf("%d,%d,%d,%.6f,%.1f\n", N, nth, bs, best, checksum);
                if (csv) fprintf(csv, "%d,%d,%d,%.8f,%.6f\n", N, nth, bs, best, checksum);
                fflush(stdout);
            }
        }

        free(A);
        free(B);
        free(C);
    }

    if (csv) fclose(csv);
    return 0;
}
