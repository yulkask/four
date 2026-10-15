#include <errno.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* Сколько секунд потомки считают ряды, прежде чем родитель пошлёт сигнал
 * на завершение. Ряды сходятся за доли миллисекунды, так что этого с запасом
 * хватает. */
#define WORK_TIME 2

enum { CHILD_PI = 0, CHILD_EXP = 1, NCHILD = 2 };

// Что потомок передаёт родителю через канал.
struct result {
	double value;    // вычисленное значение
	long terms;      // сколько членов ряда реально изменили сумму
	long iterations; // сколько раз прошёл цикл до сигнала остановки
};

/* Флаги, которые выставляет обработчик сигналов. Тип volatile sig_atomic_t
 * гарантирует корректную запись из обработчика и чтение в основном коде. */
static volatile sig_atomic_t got_start = 0; // потомок: пришёл SIGUSR1
static volatile sig_atomic_t got_stop = 0;  // потомок: пришёл SIGUSR2
static volatile sig_atomic_t got_alarm = 0; // родитель: пришёл SIGALRM

static void on_signal(int sig)
{
	if (sig == SIGUSR1)
		got_start = 1;
	else if (sig == SIGUSR2)
		got_stop = 1;
	else if (sig == SIGALRM)
		got_alarm = 1;
}

/*
 * Число pi по формуле Мэчина:
 *
 *     pi = 16*arctg(1/5) - 4*arctg(1/239),
 *     arctg(z) = z - z^3/3 + z^5/5 - z^7/7 + ...
 *
 * Оба ряда суммируются в одном цикле, каждый в свою сумму. Степени
 * не вычисляются заново: каждая получается из предыдущей умножением на z^2.
 *
 * Цикл идёт до сигнала SIGUSR2 от родителя.
 */
static void compute_pi(struct result *r)
{
	double p5 = 1.0 / 5.0;     // (1/5)^(2n+1)
	double p239 = 1.0 / 239.0; // (1/239)^(2n+1)
	const double q5 = p5 * p5;
	const double q239 = p239 * p239;
	double s5 = 0.0, s239 = 0.0; // arctg(1/5) и arctg(1/239)
	long n = 0;

	r->terms = 0;
	while (!got_stop) {
		double sign = (n % 2 == 0) ? 1.0 : -1.0;
		double next5 = s5 + sign * p5 / (2 * n + 1);
		double next239 = s239 + sign * p239 / (2 * n + 1);
		if (next5 != s5 || next239 != s239) // член ещё влияет на сумму
			r->terms = n + 1;
		s5 = next5;
		s239 = next239;
		p5 *= q5;
		p239 *= q239;
		n++;
	}
	r->iterations = n;
	r->value = 16.0 * s5 - 4.0 * s239;
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
 *
 * Цикл идёт до сигнала SIGUSR2 от родителя.
 */
static void compute_exp(double x, struct result *r)
{
	double t = x * x / 2.0;
	double term = 1.0; // t^0 / 0!
	double sum = 1.0;
	long n = 0;

	r->terms = 0;
	while (!got_stop) {
		n++;
		term = term * t / n;
		double next = sum + term;
		if (next != sum) // член ещё влияет на сумму
			r->terms = n;
		sum = next;
	}
	r->iterations = n;
	r->value = 1.0 / sum;
}

// write() может записать меньше запрошенного или прерваться сигналом.
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
 * Код процесса-потомка. Сюда попадаем сразу после fork(), когда сигналы
 * ещё заблокированы; waitmask - маска, в которой они разрешены.
 */
static void child_run(int which, double x, int wfd, const sigset_t *waitmask)
{
	static const char *const names[NCHILD] = { "pi", "exp(-x^2/2)" };
	struct result res;

	/* Ждём сигнала на старт. sigsuspend() атомарно разблокирует сигналы
	 * и засыпает, поэтому сигнал не может «проскочить» мимо. */
	while (!got_start)
		sigsuspend(waitmask);

	/* Во время счёта сигналы должны быть разрешены, иначе SIGUSR2
	 * не дойдёт до обработчика и цикл не остановится. */
	sigprocmask(SIG_SETMASK, waitmask, NULL);

	printf("  [потомок %d] pid=%d ppid=%d: получен SIGUSR1, начинаю цикл %s\n",
	       which, (int)getpid(), (int)getppid(), names[which]);
	fflush(stdout);

	// Цикл суммирования ряда - до сигнала SIGUSR2.
	if (which == CHILD_PI)
		compute_pi(&res);
	else
		compute_exp(x, &res);

	printf("  [потомок %d] pid=%d: получен SIGUSR2, цикл остановлен после "
	       "%ld итераций, отправляю результат\n",
	       which, (int)getpid(), res.iterations);
	fflush(stdout);

	if (write_full(wfd, &res, sizeof res) < 0) {
		perror("write");
		_exit(EXIT_FAILURE);
	}
	close(wfd);
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
	sigaction(SIGALRM, &sa, NULL);

	/* Блокируем сигналы до fork(): если сигнал придёт раньше, чем процесс
	 * дойдёт до ожидания, он не потеряется, а останется «отложенным»
	 * до вызова sigsuspend(). */
	sigemptyset(&block);
	sigaddset(&block, SIGUSR1);
	sigaddset(&block, SIGUSR2);
	sigaddset(&block, SIGALRM);
	sigprocmask(SIG_BLOCK, &block, &oldmask);

	// Два неименованных канала: fds[i][0] - чтение, fds[i][1] - запись.
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

	// Запуск: сначала kill(SIGUSR1), после него у потомков начинается цикл.
	for (i = 0; i < NCHILD; i++) {
		printf("[родитель] посылаю SIGUSR1 потомку %d\n", i);
		fflush(stdout);
		kill(pid[i], SIGUSR1);
	}

	/* Потомки считают параллельно. Через WORK_TIME секунд alarm() пришлёт
	 * родителю SIGALRM; до этого родитель спит в sigsuspend(). */
	alarm(WORK_TIME);
	while (!got_alarm)
		sigsuspend(&oldmask);

	// Завершение: SIGUSR2 останавливает цикл суммирования в потомках.
	for (i = 0; i < NCHILD; i++) {
		printf("[родитель] посылаю SIGUSR2 потомку %d\n", i);
		fflush(stdout);
		kill(pid[i], SIGUSR2);
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

	// Ожидание завершения потомков.
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
	printf("  pi          = %.17g  (значимых членов ряда: %ld)\n",
	       pi, res[CHILD_PI].terms);
	printf("  exp(-x^2/2) = %.17g  (значимых членов ряда: %ld)\n",
	       e, res[CHILD_EXP].terms);
	printf("  f(%g) = %.17g\n", x, f);
	printf("\nПроверка по libm: f(%g) = %.17g, разница %.3g\n",
	       x, check, fabs(f - check));
	return EXIT_SUCCESS;
}
