// Семинар 9. Задача Дирихле для уравнения Пуассона, метод Гаусса–Зейделя.
//
//   u_xx + u_yy = f(x, y) = 1,   0 < x,y < 1,   u = 0 на границе.
//
// Сетка с шагом h = 1/(N+1): внутренние узлы i,j = 1..N, на границе нули.
// Пятиточечная схема даёт формулу обновления
//   u[i,j] = (u[i-1,j] + u[i+1,j] + u[i,j-1] + u[i,j+1] - h²·f) / 4
// В методе Гаусса–Зейделя новое значение сразу пишется в сетку.
// Останов: max |u_new - u_old| < eps.
//
// Вдоль обычного обхода узел (i,j) зависит от уже обновлённых соседей
// (i-1,j) и (i,j-1), поэтому цикл по узлам нельзя просто разрезать между
// потоками. Соседи клетки всегда другого цвета шахматной раскраски
// (i+j чётное / нечётное), поэтому параллельная версия — красно-чёрный
// Гаусс–Зейдель: все красные узлы обновляются параллельно, барьер,
// затем все чёрные.
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <omp.h>

// Итог одного прогона: время, число итераций, последняя невязка и
// минимальное значение на сетке (решение этой задачи отрицательное).
struct Run {
    double seconds;
    int iters;
    double dmax;
    double umin;
};

// Минимум по внутренним узлам. Граница в подсчёт не входит: там заведомо 0.
static double grid_min(const double* u, int N) {
    int M = N + 2;   // узлы 0..N+1, внутри 1..N, по краям лежит граница
    double m = 0.0;
    for (int i = 1; i <= N; i++)
        for (int j = 1; j <= N; j++) {
            double v = u[i * M + j];
            if (v < m) m = v;
        }
    return m;
}

// Последовательный обход по строкам. Сосед слева и сосед сверху уже новые.
static Run gauss_seidel_serial(double* u, int N, double h2, double eps, int max_iters) {
    int M = N + 2;
    double t0 = omp_get_wtime();
    int it = 0;
    double dmax = 0.0;
    do {
        dmax = 0.0;
        for (int i = 1; i <= N; i++) {
            double* row = u + i * M;            // текущая строка
            const double* up = u + (i - 1) * M; // сосед сверху, уже обновлён
            const double* dn = u + (i + 1) * M; // сосед снизу, ещё старый
            for (int j = 1; j <= N; j++) {
                double old = row[j];
                // row[j-1] уже новый, row[j+1] ещё старый — это и есть Гаусс–Зейдель.
                // h2 = h²·f, f = 1, поэтому правая часть вычитается как h².
                double neu = 0.25 * (up[j] + dn[j] + row[j - 1] + row[j + 1] - h2);
                row[j] = neu;
                double d = fabs(neu - old);
                if (d > dmax) dmax = d;
            }
        }
        it++;
        // Пока самая большая поправка больше порога, делаем ещё проход.
    } while (dmax > eps && it < max_iters);
    Run r;
    r.seconds = omp_get_wtime() - t0;
    r.iters = it;
    r.dmax = dmax;
    r.umin = grid_min(u, N);
    return r;
}

// Красно-чёрный обход. Внутри одного цвета узлы не соседствуют,
// запись u[i,j] не мешает другим потокам.
static Run gauss_seidel_redblack(double* u, int N, double h2, double eps, int max_iters) {
    int M = N + 2;
    double t0 = omp_get_wtime();
    int it = 0;
    double dmax = 0.0;
    do {
        dmax = 0.0;
        // color = 0 — чётная сумма i+j, color = 1 — нечётная.
        // Внутри одного цвета потоки пишут в разные ячейки.
        for (int color = 0; color < 2; color++) {
            // reduction(max) собирает наибольшую поправку со всех потоков.
            // В конце omp for стоит барьер: второй цвет стартует, когда первый уже записан.
#pragma omp parallel for reduction(max : dmax) schedule(static)
            for (int i = 1; i <= N; i++) {
                double* row = u + i * M;
                const double* up = u + (i - 1) * M;
                const double* dn = u + (i + 1) * M;
                // Первый столбец нужного цвета в этой строке: 1 или 2.
                // Дальше шаг 2 — берём каждую вторую клетку.
                int j0 = (((i + 1) & 1) == color) ? 1 : 2;
                for (int j = j0; j <= N; j += 2) {
                    double old = row[j];
                    double neu = 0.25 * (up[j] + dn[j] + row[j - 1] + row[j + 1] - h2);
                    row[j] = neu;
                    double d = fabs(neu - old);
                    if (d > dmax) dmax = d;
                }
            }
        }
        it++;
    } while (dmax > eps && it < max_iters);
    Run r;
    r.seconds = omp_get_wtime() - t0;
    r.iters = it;
    r.dmax = dmax;
    r.umin = grid_min(u, N);
    return r;
}

// Сетка (N+2)×(N+2). calloc обнуляет и границу, и внутренние узлы:
// начальное приближение u = 0, краевое условие тоже 0.
static double* alloc_grid(int N) {
    int M = N + 2;
    double* u = (double*)calloc((size_t)M * M, sizeof(double));
    if (!u) {
        fprintf(stderr, "Недостаточно памяти для N=%d\n", N);
        exit(1);
    }
    return u;
}

static double max_diff(const double* a, const double* b, int N) {
    int M = N + 2;
    double m = 0.0;
    for (int i = 1; i <= N; i++)
        for (int j = 1; j <= N; j++) {
            double d = fabs(a[i * M + j] - b[i * M + j]);
            if (d > m) m = d;
        }
    return m;
}

int main() {
    const double eps = 1e-4;                       // порог из задания
    const int repeats = 5;                          // в таблицу берём лучший из пяти
    int sizes[] = {10, 100, 1000, 2000, 3000};      // размеры сетки N
    int n_sizes = 5;
    int threads[] = {2, 4, 8};
    int n_threads = 3;

    // Не давать OpenMP самому менять число потоков.
    omp_set_dynamic(0);

    // Обе схемы сходятся к одному решению. На N=10 после 400 итераций
    // сетки должны совпасть с точностью округления.
    {
        const int N = 10;
        double h2 = 1.0 / (N + 1) / (N + 1);   // h² при f = 1
        double* a = alloc_grid(N);
        double* b = alloc_grid(N);
        omp_set_num_threads(4);
        // eps = 0, поэтому останов только по числу итераций, а не по порогу.
        Run rs = gauss_seidel_serial(a, N, h2, 0.0, 400);
        Run rp = gauss_seidel_redblack(b, N, h2, 0.0, 400);
        printf("Проверка N=10, 400 итераций: max|serial-redblack|=%.3e  u_min=%.6f\n",
               max_diff(a, b, N), rs.umin);
        (void)rp;
        free(a);
        free(b);
    }

    FILE* csv = fopen("results/seminar9_gs.csv", "w");
    if (!csv) {
        perror("results/seminar9_gs.csv");
        return 1;
    }
    fprintf(csv, "n,version,threads,time_sec,speedup,iters,dmax,umin\n");

    printf("\n%6s %10s %12s %10s %8s %12s\n",
           "N", "потоки", "время, с", "ускорение", "итерации", "u_min");

    for (int s = 0; s < n_sizes; s++) {
        int N = sizes[s];
        double h2 = 1.0 / (N + 1) / (N + 1);   // h = 1/(N+1), здесь сразу h²
        double* u = alloc_grid(N);

        // fn — последовательный или красно-чёрный решатель.
        // Сетка перед каждым замером обнуляется, иначе останется решение прошлого прогона.
        // Первый вызов — прогрев, его время выбрасывается.
        auto measure = [&](Run (*fn)(double*, int, double, double, int), int warmup_threads) -> Run {
            omp_set_num_threads(warmup_threads);
            memset(u, 0, (size_t)(N + 2) * (N + 2) * sizeof(double));
            fn(u, N, h2, eps, 1000000);
            Run best;
            best.seconds = 1e300;
            best.iters = 0;
            best.dmax = 0;
            best.umin = 0;
            for (int r = 0; r < repeats; r++) {
                memset(u, 0, (size_t)(N + 2) * (N + 2) * sizeof(double));
                Run cur = fn(u, N, h2, eps, 1000000);
                if (cur.seconds < best.seconds) best = cur;
            }
            return best;
        };

        // Последовательное время — знаменатель ускорения S = Tпосл / Tp.
        Run serial = measure(gauss_seidel_serial, 1);
        printf("%6d %10s %12.6f %10s %8d %12.6f\n",
               N, "посл.", serial.seconds, "—", serial.iters, serial.umin);
        fprintf(csv, "%d,serial,1,%.8f,1.0,%d,%.6e,%.8f\n",
                N, serial.seconds, serial.iters, serial.dmax, serial.umin);

        // Один поток красно-чёрной схемы — чтобы видеть, какая часть
        // ускорения от самой раскраски, а какая от OpenMP.
        Run rb1 = measure(gauss_seidel_redblack, 1);
        printf("%6d %10s %12.6f %10.4f %8d %12.6f\n",
               N, "кч-1", rb1.seconds, serial.seconds / rb1.seconds, rb1.iters, rb1.umin);
        fprintf(csv, "%d,redblack,1,%.8f,%.6f,%d,%.6e,%.8f\n",
                N, rb1.seconds, serial.seconds / rb1.seconds, rb1.iters, rb1.dmax, rb1.umin);

        for (int t = 0; t < n_threads; t++) {
            int p = threads[t];
            Run par = measure(gauss_seidel_redblack, p);
            // Ускорение относительно последовательного обхода, не относительно одного потока.
            double speedup = serial.seconds / par.seconds;
            printf("%6d %10d %12.6f %10.4f %8d %12.6f\n",
                   N, p, par.seconds, speedup, par.iters, par.umin);
            fprintf(csv, "%d,redblack,%d,%.8f,%.6f,%d,%.6e,%.8f\n",
                    N, p, par.seconds, speedup, par.iters, par.dmax, par.umin);
        }
        free(u);
        fflush(csv);
        fflush(stdout);
    }

    fclose(csv);
    printf("\nCSV: results/seminar9_gs.csv\n");
    return 0;
}
