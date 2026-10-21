/* Первая программа: читает числа с клавиатуры, кладёт их в разделяемую
 * память и ждёт, пока вторая программа (check) запишет ответ. */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/shm.h>
#include <sys/types.h>
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
	int shmid;
	struct shared *shm;
	char line[128];
	unsigned long long n;

	if ((key = ftok(KEY_FILE, KEY_PROJ)) == -1) {
		perror("ftok");
		return 1;
	}
	if ((shmid = shmget(key, sizeof(struct shared), 0644 | IPC_CREAT)) == -1) {
		perror("shmget");
		return 1;
	}
	shm = shmat(shmid, NULL, 0);
	if (shm == (void *)-1) {
		perror("shmat");
		return 1;
	}
	// Сбрасываем состояние, если прошлый запуск был прерван посередине.
	atomic_store(&shm->state, ST_EMPTY);

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

		// 1. Помещаем число в память и сообщаем, что есть запрос.
		shm->value = n;
		atomic_store(&shm->state, ST_REQUEST);
		printf("Число %llu записано в разделяемую память\n", n);

		// 3. Проверяем память, пока вторая программа не запишет ответ.
		int waited = 0;
		while (atomic_load(&shm->state) != ST_DONE) {
			if (++waited == 100) // ~1 с
				printf("Ждём ответа от ./check...\n");
			usleep(POLL_USEC);
		}
		printf("Ответ из памяти: %llu — %s\n\n", shm->value,
		       verdict_text(shm->verdict));
		atomic_store(&shm->state, ST_EMPTY);
	}

	// Сообщаем второй программе, что запросов больше не будет.
	atomic_store(&shm->state, ST_QUIT);
	if (shmdt(shm) == -1) {
		perror("shmdt");
		return 1;
	}
	/* Помечаем сегмент на удаление: он исчезнет, когда от него
	 * отсоединится и вторая программа. */
	if (shmctl(shmid, IPC_RMID, NULL) == -1) {
		perror("shmctl");
		return 1;
	}
	return 0;
}
