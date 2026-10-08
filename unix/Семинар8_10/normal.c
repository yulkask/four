#include <errno.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* Суммирование прекращается, когда очередной член ряда становится
 * пренебрежимо мал по сравнению с уже накопленной суммой. */
#define EPS 1e-17

enum { CHILD_PI = 0, CHILD_EXP = 1, NCHILD = 2 };

// Что потомок передаёт родителю через канал. 
struct result {
	double value; // вычисленное значение 
	long terms;   // сколько членов ряда понадобилось 
};

/* Флаги, которые выставляет обработчик сигналов. Тип volatile sig_atomic_t
 * гарантирует корректную запись из обработчика и чтение в основном коде. */
static volatile sig_atomic_t got_start = 0;
static volatile sig_atomic_t got_stop = 0;

static void on_signal(int sig)
{
	if (sig == SIGUSR1)
		got_start = 1;
	else if (sig == SIGUSR2)
		got_stop = 1;
}

/*
 * arctg(z) = z - z^3/3 + z^5/5 - z^7/7 + ...      (|z| < 1)
 *
 * Степень z^(2n+1) не вычисляется заново на каждом шаге: она получается
 * из предыдущей умножением на z^2.
 */
static double arctan_series(double z, long *terms)
{
	double z2 = z * z;
	double power = z; /* z^(2n+1) */
	double sum = 0.0;
	long n = 0;

	for (;;) {
		double term = power / (2 * n + 1);
		if (term < EPS * fabs(sum))
			break;
		sum += (n % 2 == 0) ? term : -term;
		power *= z2;
		n++;
	}
	*terms += n;
	return sum;
}

// Формула Мэчина: pi = 16*arctg(1/5) - 4*arctg(1/239). 
static double compute_pi(long *terms)
{
	*terms = 0;
	return 16.0 * arctan_series(1.0 / 5.0, terms)
	     - 4.0 * arctan_series(1.0 / 239.0, terms);
}

/*
 * exp(-t), t = x^2/2 >= 0.
 *
 * Знакопеременный ряд 1 - t + t^2/2! - t^3/3! + ... при больших t теряет
 * точность из-за вычитания больших близких чисел, поэтому считаем ряд
 * с положительными членами и берём обратную величину:
 *
 *     exp(-t) = 1 / exp(t) = 1 / (1 + t + t^2/2! + t^3/3! + ...)
 *
 * Факториал отдельно не вычисляется: каждый член получается из предыдущего
 * умножением на t и делением на номер шага n:  t^n/n! = (t^(n-1)/(n-1)!) * t / n.
 */
static double compute_exp(double x, long *terms)
{
	double t = x * x / 2.0;
	double term = 1.0; /* t^0 / 0! */
	double sum = 1.0;
	long n = 0;

	while (term > EPS * sum) {
		n++;
		term = term * t / n;
		sum += term;
	}
	*terms = n;
	return 1.0 / sum;
}

// запись в канал
static int write_full(int fd, const void *buf, size_t len)
{
	const char *p = buf;
	while (len > 0) {
		ssize_t n = write(fd, p, len);
		if (n < 0) {
			if (errno == EINTR)
				continue;
			return -1;
		}
		p += n;
		len -= (size_t)n;
	}
	return 0;
}

// Возвращает 0, если прочитано ровно len байт, иначе -1. 
static int read_full(int fd, void *buf, size_t len)
{
	char *p = buf;
	while (len > 0) {
		ssize_t n = read(fd, p, len);
		if (n < 0) {
			if (errno == EINTR)
				continue;
			return -1;
		}
		// канал закрыт раньше, чем пришли данные
		if (n == 0)
			return -1;
		p += n;
		len -= (size_t)n;
	}
	return 0;
}

/*
 * Код процесса-потомка. Сюда попадаем сразу после fork(), когда SIGUSR1
 * и SIGUSR2 ещё заблокированы; waitmask - маска, в которой они разрешены.
 */
static void child_run(int which, double x, int wfd, const sigset_t *waitmask)
{
	static const char *const names[NCHILD] = { "pi", "exp(-x^2/2)" };
	struct result res;

	/* Ждём сигнала на старт. sigsuspend() атомарно разблокирует сигналы
	 * и засыпает, поэтому сигнал не может пройти мимо. */
	while (!got_start)
		sigsuspend(waitmask);

	printf("  [потомок %d] pid=%d ppid=%d: получен SIGUSR1, вычисляю %s\n",
	       which, (int)getpid(), (int)getppid(), names[which]);
	fflush(stdout);

	if (which == CHILD_PI)
		res.value = compute_pi(&res.terms);
	else
		res.value = compute_exp(x, &res.terms);

	if (write_full(wfd, &res, sizeof res) < 0) {
		perror("write");
		_exit(EXIT_FAILURE);
	}
	close(wfd);

	// Результат отправлен - ждём сигнала на завершение.
	while (!got_stop)
		sigsuspend(waitmask);

	printf("  [потомок %d] pid=%d: получен SIGUSR2, завершаюсь\n",
	       which, (int)getpid());
	fflush(stdout);
	exit(EXIT_SUCCESS);
}

static int parse_x(int argc, char *argv[], double *x)
{
	char buf[128];
	const char *s;
	char *end;

	if (argc > 2) {
		fprintf(stderr, "Использование: %s [x]\n", argv[0]);
		return -1;
	}
	if (argc == 2) {
		s = argv[1];
	} else {
		printf("Введите x: ");
		fflush(stdout);
		if (fgets(buf, sizeof buf, stdin) == NULL)
			return -1;
		s = buf;
	}

	errno = 0;
	*x = strtod(s, &end);
	while (*end == ' ' || *end == '\t' || *end == '\n')
		end++;
	if (end == s || *end != '\0' || errno == ERANGE || !isfinite(*x)) {
		fprintf(stderr, "Некорректное значение x: %s\n", s);
		return -1;
	}
	return 0;
}

int main(int argc, char *argv[])
{
	struct sigaction sa;
	sigset_t block, oldmask;
	int fds[NCHILD][2];
	pid_t pid[NCHILD];
	struct result res[NCHILD];
	double x;
	int i, j, ok = 1;

	if (parse_x(argc, argv, &x) < 0)
		return EXIT_FAILURE;

	/* Обработчик сигналов. Устанавливается до fork(), поэтому потомки
	 * наследуют его и готовы принять сигнал с первой же инструкции. */
	memset(&sa, 0, sizeof sa);
	sa.sa_handler = on_signal;
	sigemptyset(&sa.sa_mask);
	sigaction(SIGUSR1, &sa, NULL);
	sigaction(SIGUSR2, &sa, NULL);

	/* Блокируем SIGUSR1/SIGUSR2 до fork(): если родитель пошлёт сигнал
	 * раньше, чем потомок дойдёт до ожидания, сигнал не потеряется,
	 * а останется «отложенным» до вызова sigsuspend(). */
	sigemptyset(&block);
	sigaddset(&block, SIGUSR1);
	sigaddset(&block, SIGUSR2);
	sigprocmask(SIG_BLOCK, &block, &oldmask);

	//Два неименованных канала: fds[i][0] - чтение, fds[i][1] - запись.
	for (i = 0; i < NCHILD; i++) {
		if (pipe(fds[i]) < 0) {
			perror("pipe");
			return EXIT_FAILURE;
		}
	}

	printf("[родитель] pid=%d, x=%g\n", (int)getpid(), x);

	// Порождаем потомков.
	for (i = 0; i < NCHILD; i++) {
		/* Сбрасываем буфер stdout, иначе его содержимое скопируется
		 * в потомка и будет напечатано дважды. */
		fflush(stdout);
		pid[i] = fork();
		if (pid[i] < 0) {
			perror("fork");
			for (j = 0; j < i; j++)
				kill(pid[j], SIGKILL);
			while (wait(NULL) > 0)
				;
			return EXIT_FAILURE;
		}
		if (pid[i] == 0) {
			// Потомок оставляет себе только конец записи своего канала. 
			for (j = 0; j < NCHILD; j++) {
				close(fds[j][0]);
				if (j != i)
					close(fds[j][1]);
			}
			child_run(i, x, fds[i][1], &oldmask);
		}
		printf("[родитель] порождён потомок %d, pid=%d\n", i, (int)pid[i]);
	}

	/* Родитель только читает: закрываем концы записи. Тогда, если потомок
	 * завершится, не записав результат, read() вернёт 0, а не зависнет. */
	for (i = 0; i < NCHILD; i++)
		close(fds[i][1]);
	sigprocmask(SIG_SETMASK, &oldmask, NULL);

	// Сигнал на старт - оба потомка начинают считать параллельно. 
	for (i = 0; i < NCHILD; i++) {
		printf("[родитель] посылаю SIGUSR1 потомку %d\n", i);
		fflush(stdout);
		kill(pid[i], SIGUSR1);
	}

	// Читаем результаты из каналов (read блокируется до их появления). 
	for (i = 0; i < NCHILD; i++) {
		if (read_full(fds[i][0], &res[i], sizeof res[i]) < 0) {
			fprintf(stderr, "[родитель] не удалось получить результат "
			                "от потомка %d\n", i);
			ok = 0;
		}
		close(fds[i][0]);
	}

	// Сигнал на завершение и ожидание потомков. 
	for (i = 0; i < NCHILD; i++) {
		printf("[родитель] посылаю SIGUSR2 потомку %d\n", i);
		fflush(stdout);
		kill(pid[i], SIGUSR2);
	}
	for (i = 0; i < NCHILD; i++) {
		int status;
		pid_t done = wait(&status);
		if (done < 0) {
			perror("wait");
			ok = 0;
			break;
		}
		if (WIFEXITED(status)) {
			printf("[родитель] потомок pid=%d завершился, код %d\n",
			       (int)done, WEXITSTATUS(status));
			if (WEXITSTATUS(status) != 0)
				ok = 0;
		} else if (WIFSIGNALED(status)) {
			printf("[родитель] потомок pid=%d убит сигналом %d\n",
			       (int)done, WTERMSIG(status));
			ok = 0;
		}
	}

	if (!ok)
		return EXIT_FAILURE;

	// Итог
	double pi = res[CHILD_PI].value;
	double e = res[CHILD_EXP].value;
	double f = e / sqrt(2.0 * pi);
	double check = exp(-x * x / 2.0) / sqrt(2.0 * M_PI);

	printf("\nРезультаты:\n");
	printf("  pi          = %.17g  (%ld членов ряда)\n",
	       pi, res[CHILD_PI].terms);
	printf("  exp(-x^2/2) = %.17g  (%ld членов ряда)\n",
	       e, res[CHILD_EXP].terms);
	printf("  f(%g) = %.17g\n", x, f);
	printf("\nПроверка по libm: f(%g) = %.17g, разница %.3g\n",
	       x, check, fabs(f - check));
	return EXIT_SUCCESS;
}
