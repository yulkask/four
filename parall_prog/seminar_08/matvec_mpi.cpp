// Семинар 8. Умножение матрицы 1000×1000 на вектор, MPI
//
// Матрица и вектор сначала лежат у процесса 0. Дальше:
//   1. MPI_Scatter — каждому процессу достаётся непрерывный блок строк A
//   2. MPI_Bcast   — вектор b рассылается всем (он нужен каждому целиком)
//   3. локально    — c_i = Σ_j a_ij * b_j только по своим строкам
//   4. MPI_Gather  — куски результата собираются у процесса 0
//
// A[i][j] = 1 + (i + j) % 7, b[j] = 1 — та же формула, что в семинаре 3,
// результат можно сверить с последовательным умножением.
#include <mpi.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

// Элемент матрицы по индексам строки и столбца. Матрицу не храним
// в последовательной версии: значение и так восстанавливается формулой.
static double aij(int i, int j) {
    return 1.0 + (double)((i + j) % 7);
}

// Последовательное умножение на процессе 0. Это база для ускорения:
// S = T_посл / T_MPI. MPI здесь не участвует.
static double sequential(const double* b, double* c, int n) {
    double t0 = MPI_Wtime();
    for (int i = 0; i < n; i++) {
        double sum = 0.0;
        // c[i] — скалярное произведение i-й строки на вектор b
        for (int j = 0; j < n; j++) sum += aij(i, j) * b[j];
        c[i] = sum;
    }
    return MPI_Wtime() - t0;
}

int main(int argc, char** argv) {
    // MPI_Init поднимает процессы, запущенные через mpirun -n p.
    // rank — номер этого процесса (0..p-1), size — сколько их всего.
    MPI_Init(&argc, &argv);
    int rank = 0, size = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    const int n = 1000;
    // Строки делятся поровну, поэтому n должно делиться на число процессов.
    if (n % size != 0) {
        if (rank == 0)
            fprintf(stderr, "1000 не делится на %d процессов\n", size);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    const int rows = n / size;   // сколько строк достанется каждому процессу

    double* A = nullptr;          // полная матрица, только у процесса 0
    double* c = nullptr;          // полный результат, только у процесса 0
    double* c_seq = nullptr;
    if (rank == 0) {
        A = (double*)malloc((size_t)n * n * sizeof(double));
        c = (double*)malloc((size_t)n * sizeof(double));
        c_seq = (double*)malloc((size_t)n * sizeof(double));
        if (!A || !c || !c_seq) {
            fprintf(stderr, "Недостаточно памяти\n");
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
        // Матрица лежит в памяти построчно: элемент (i, j) по адресу i*n + j.
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) A[i * n + j] = aij(i, j);
    }

    // b, свой кусок матрицы и свой кусок результата есть у каждого процесса.
    double* b = (double*)malloc((size_t)n * sizeof(double));
    double* A_local = (double*)malloc((size_t)rows * n * sizeof(double));
    double* c_local = (double*)malloc((size_t)rows * sizeof(double));
    if (!b || !A_local || !c_local) {
        fprintf(stderr, "Недостаточно памяти на процессе %d\n", rank);
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    for (int j = 0; j < n; j++) b[j] = 1.0;

    const int repeats = 20;
    double best = 1e300;
    double best_scatter = 0, best_bcast = 0, best_compute = 0, best_gather = 0;

    // Первый проход прогревает процессы и не входит в замер.
    // Барьер перед стартом нужен, чтобы все процессы начали одновременно.
    for (int r = 0; r < repeats + 1; r++) {
        MPI_Barrier(MPI_COMM_WORLD);
        double t0 = MPI_Wtime();

        // Scatter режет массив A на равные куски и отдаёт каждому свой.
        // sendcount — длина куска одного процесса, а не всей матрицы.
        // На процессах, кроме нулевого, буфер A не используется.
        double ts = MPI_Wtime();
        MPI_Scatter(A, rows * n, MPI_DOUBLE,
                    A_local, rows * n, MPI_DOUBLE, 0, MPI_COMM_WORLD);
        ts = MPI_Wtime() - ts;

        // Вектор b нужен всем целиком: строка умножается на весь b.
        double tb = MPI_Wtime();
        MPI_Bcast(b, n, MPI_DOUBLE, 0, MPI_COMM_WORLD);
        tb = MPI_Wtime() - tb;

        // Локальная строка i — это глобальная строка rank*rows + i.
        // Считает только этот процесс, чужие строки ему не нужны.
        double tc = MPI_Wtime();
        for (int i = 0; i < rows; i++) {
            const double* a = A_local + (size_t)i * n;
            double sum = 0.0;
            for (int j = 0; j < n; j++) sum += a[j] * b[j];
            c_local[i] = sum;
        }
        tc = MPI_Wtime() - tc;

        // Gather склеивает куски c в том же порядке, в каком Scatter резал A:
        // сначала строки процесса 0, потом процесса 1 и так далее.
        double tg = MPI_Wtime();
        MPI_Gather(c_local, rows, MPI_DOUBLE, c, rows, MPI_DOUBLE, 0, MPI_COMM_WORLD);
        tg = MPI_Wtime() - tg;

        MPI_Barrier(MPI_COMM_WORLD);
        double total = MPI_Wtime() - t0;
        // В зачёт идёт самый быстрый проход. Фазы берём из того же прохода.
        if (r > 0 && rank == 0 && total < best) {
            best = total;
            best_scatter = ts;
            best_bcast = tb;
            best_compute = tc;
            best_gather = tg;
        }
    }

    if (rank == 0) {
        double best_seq = 1e300;
        for (int r = 0; r < repeats; r++) {
            double t = sequential(b, c_seq, n);
            if (t < best_seq) best_seq = t;
        }
        // Сверка: параллельный результат должен совпасть с последовательным.
        double max_diff = 0.0;
        double checksum = 0.0;
        for (int i = 0; i < n; i++) {
            double d = fabs(c[i] - c_seq[i]);
            if (d > max_diff) max_diff = d;
            checksum += c[i];
        }
        double speedup = best_seq / best;
        printf("processes=%d rows_per_process=%d\n", size, rows);
        printf("time_parallel=%.6f s   (scatter %.6f, bcast %.6f, compute %.6f, gather %.6f)\n",
               best, best_scatter, best_bcast, best_compute, best_gather);
        printf("time_sequential=%.6f s   speedup=%.4f\n", best_seq, speedup);
        printf("max|c_mpi - c_seq|=%.3e   checksum=%.6f\n", max_diff, checksum);

        // Вектор из 1000 чисел периодичен с периодом 7: в каждой строке
        // 142 полных цикла остатков 0..6 (сумма 28 на цикл = 3976) и ещё
        // 6 элементов. Отсюда c[i] зависит только от i mod 7.
        const double by_residue[7] = {3997, 4003, 4002, 4001, 4000, 3999, 3998};
        printf("\nРешение c = A*b. Первые 14 элементов (два периода):\n");
        printf("%6s %12s %12s %12s\n", "i", "MPI", "послед.", "формула");
        int formula_mismatch = 0;
        for (int i = 0; i < n; i++) {
            double expect = by_residue[i % 7];
            if (c[i] != expect || c_seq[i] != expect) formula_mismatch++;
            if (i < 14)
                printf("%6d %12.0f %12.0f %12.0f\n", i, c[i], c_seq[i], expect);
        }
        printf("Дальше значения повторяются: 3997, 4003, 4002, 4001, 4000, 3999, 3998.\n");
        printf("С формулой не сошлось элементов: %d из %d\n", formula_mismatch, n);

        FILE* sol = fopen("seminar_08/solution.txt", "w");
        if (sol) {
            fprintf(sol, "i\tc_mpi\tc_sequential\tc_formula\n");
            for (int i = 0; i < n; i++)
                fprintf(sol, "%d\t%.0f\t%.0f\t%.0f\n", i, c[i], c_seq[i], by_residue[i % 7]);
            fclose(sol);
            printf("Полный вектор: seminar_08/solution.txt\n");
        }

        FILE* csv = fopen("results/seminar8_matvec.csv", "a");
        if (csv) {
            fprintf(csv, "%d,%.8f,%.8f,%.8f,%.8f,%.8f,%.8f,%.6f,%.3e\n",
                    size, best, best_scatter, best_bcast, best_compute, best_gather,
                    best_seq, speedup, max_diff);
            fclose(csv);
        }
        free(A);
        free(c);
        free(c_seq);
    }

    free(b);
    free(A_local);
    free(c_local);
    MPI_Finalize();
    return 0;
}
