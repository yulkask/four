/* Первая программа: читает числа с клавиатуры, отправляет их в очередь
 * сообщений и получает из очереди ответ второй программы (check). */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/msg.h>
#include <unistd.h>

#include "common.h"

// Разбирает строку как неотрицательное целое. Возвращает 0 при успехе.
static int parse_number(const char *s, unsigned long long *out)
{
	char *end;

	while (*s == ' ' || *s == '\t')
		s++;
	if (*s == '-' || *s == '\0' || *s == '\n')
		return -1;
	errno = 0;
	*out = strtoull(s, &end, 10);
	if (errno != 0 || end == s)
		return -1;
	while (*end == ' ' || *end == '\t' || *end == '\n')
		end++;
	return *end == '\0' ? 0 : -1;
}

static const char *verdict_text(int v)
{
	switch (v) {
	case V_PRIME:
		return "простое";
	case V_COMPOSITE:
		return "составное";
	default:
		return "ни простое, ни составное";
	}
}

int main(void)
{
	key_t key;
	int msgid;
	struct message msg;
	char line[128];
	unsigned long long n;
	pid_t me = getpid();

	if ((key = ftok(KEY_FILE, KEY_PROJ)) == -1) {
		perror("ftok");
		return 1;
	}
	/* Очередь создаёт вторая программа. Без IPC_CREAT msgget вернёт ошибку,
	 * если она ещё не запущена. */
	if ((msgid = msgget(key, 0)) == -1) {
		if (errno == ENOENT)
			fprintf(stderr, "Очереди нет: сначала запустите ./check\n");
		else
			perror("msgget");
		return 1;
	}

	for (;;) {
		printf("Введите число (Ctrl+D — выход): ");
		fflush(stdout);
		if (fgets(line, sizeof line, stdin) == NULL) {
			putchar('\n');
			break;
		}
		if (parse_number(line, &n) != 0) {
			printf("Нужно неотрицательное целое число до %llu\n",
			       (unsigned long long)-1);
			continue;
		}

		// 1. Помещаем число в очередь.
		msg.mtype = MT_REQUEST;
		msg.pid = me;
		msg.value = n;
		msg.verdict = V_NONE;
		if (msgsnd(msgid, &msg, MSG_SIZE, 0) == -1) {
			perror("msgsnd");
			return 1;
		}
		printf("Число %llu отправлено в очередь\n", n);

		// 3. Ждём в очереди сообщение с типом, равным нашему pid.
		if (msgrcv(msgid, &msg, MSG_SIZE, me, 0) == -1) {
			if (errno == EIDRM)
				fprintf(stderr, "Очередь удалена: ./check завершился\n");
			else
				perror("msgrcv");
			return 1;
		}
		printf("Ответ из очереди: %llu — %s\n\n", msg.value,
		       verdict_text(msg.verdict));
	}
	return 0;
}
