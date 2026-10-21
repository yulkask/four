/* Вторая программа: создаёт очередь сообщений, получает из неё числа,
 * проверяет их на простоту и отправляет ответ обратно в очередь.
 * Завершается по Ctrl+C (или kill) и удаляет очередь. */
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/msg.h>

#include "common.h"

static volatile sig_atomic_t got_stop = 0;

static void on_signal(int sig)
{
	(void)sig;
	got_stop = 1;
}

// Перебор делителей 2, 3 и 6k±1 до корня из n.
static int check_prime(unsigned long long n)
{
	if (n < 2)
		return V_NONE;
	if (n < 4)
		return V_PRIME;
	if (n % 2 == 0 || n % 3 == 0)
		return V_COMPOSITE;
	// Условие i <= n / i вместо i * i <= n, чтобы не было переполнения.
	for (unsigned long long i = 5; i <= n / i; i += 6)
		if (n % i == 0 || n % (i + 2) == 0)
			return V_COMPOSITE;
	return V_PRIME;
}

int main(void)
{
	key_t key;
	int msgid;
	struct message msg;
	struct sigaction sa;
	int rc = 0;

	/* Обработчик только ставит флаг. SA_RESTART не задан, поэтому msgrcv прерывается с EINTR,
	 * цикл заканчивается, и очередь удаляется в main. */
	memset(&sa, 0, sizeof sa);
	sa.sa_handler = on_signal;
	sigemptyset(&sa.sa_mask);
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGTERM, &sa, NULL);
	sigaction(SIGHUP, &sa, NULL);

	if ((key = ftok(KEY_FILE, KEY_PROJ)) == -1) {
		perror("ftok");
		return 1;
	}
	if ((msgid = msgget(key, 0644 | IPC_CREAT)) == -1) {
		perror("msgget");
		return 1;
	}

	printf("Ожидание чисел в очереди (Ctrl+C — выход)...\n");
	while (!got_stop) {
		// 2. Берём из очереди только запросы (тип MT_REQUEST).
		if (msgrcv(msgid, &msg, MSG_SIZE, MT_REQUEST, 0) == -1) {
			if (errno == EINTR)
				continue; // пришёл сигнал, проверим флаг
			perror("msgrcv");
			rc = 1;
			break;
		}
		msg.verdict = check_prime(msg.value);
		printf("От pid %d получено %llu -> %s\n", (int)msg.pid, msg.value,
		       msg.verdict == V_PRIME ? "простое" :
		       msg.verdict == V_COMPOSITE ? "составное" : "ни то, ни другое");

		// Ответ адресуем спросившему процессу: тип = его pid.
		msg.mtype = msg.pid;
		if (msgsnd(msgid, &msg, MSG_SIZE, 0) == -1) {
			perror("msgsnd");
			rc = 1;
			break;
		}
	}

	if (msgctl(msgid, IPC_RMID, NULL) == -1) {
		perror("msgctl");
		return 1;
	}
	printf("\nОчередь удалена\n");
	return rc;
}
