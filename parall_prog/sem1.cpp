#include <iostream>
#include <clocale>
#include <omp.h>

using namespace std;

bool isPrime(int n) {
    if (n < 2)      return false;
    if (n == 2)     return true;
    if (n % 2 == 0) return false;          // чётные > 2 не простые
    for (int i = 3; i * i <= n; i += 2) {  // только нечётные делители до sqrt(n)
        if (n % i == 0) return false;
    }
    return true;
}

int main() {
    setlocale(LC_ALL, "Russian");

#ifdef _OPENMP
    cout << "Поддержка OpenMP включена" << endl;
#else
    cout << "OpenMP не поддерживается" << endl;
#endif

    const int N = 100000;   // верхняя граница диапазона
    const int REQUESTED = 8;        // запрашиваемое число потоков

    // Задание 1 ч1 — задать количество потоков

    omp_set_num_threads(REQUESTED);
    cout << "Запрошено потоков: " << REQUESTED << "\n";
    cout << "Вне параллельной области omp_get_num_threads() = "
        << omp_get_num_threads()
        << "  (вне parallel это всегда 1)\n";

    int tid;
    long long sum = 0;   // long long — иначе переполнение int

    // Задание 1 ч3 — замер времени

    double wtime;
    wtime = omp_get_wtime();

    // Задание 1 ч2 — сумма простых чисел на [2; 100000] через reduction

#pragma omp parallel private(tid) reduction(+ : sum)
    {
        // Идентификатор потока и реальное количество потоков (один поток)
#pragma omp single
        cout << "Реально запущено потоков: " << omp_get_num_threads() << endl;

        tid = omp_get_thread_num();

        // Проверка, сколько потоков получилось (задание 1 ч1)
#pragma omp critical
        cout << "Работает поток с id = " << tid << endl;

#pragma omp for
        for (int i = 2; i <= N; ++i) {
            if (isPrime(i)) sum += i;
        }
    }

    wtime = omp_get_wtime() - wtime;

    cout << "Сумма простых чисел от 2 до " << N << " = " << sum << "\n";
    cout << "Время выполнения: " << wtime << " сек.\n";

    return 0;
}