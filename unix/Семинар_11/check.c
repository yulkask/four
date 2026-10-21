/* Вторая программа: берёт число из разделяемой памяти, проверяет его на
 * простоту и записывает результат обратно. */
#include <stdio.h>
#include <sys/shm.h>
#include <sys/types.h>
#include <unistd.h>

#include "common.h"

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
	int shmid;
	struct shared *shm;
	int st;

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

	printf("Ожидание чисел в разделяемой памяти...\n");
	while ((st = atomic_load(&shm->state)) != ST_QUIT) {
		if (st != ST_REQUEST) {
			usleep(POLL_USEC);
			continue;
		}
		// 2. Получаем число, проверяем, кладём результат обратно.
		unsigned long long n = shm->value;
		shm->verdict = check_prime(n);
		printf("Получено %llu -> %s\n", n,
		       shm->verdict == V_PRIME ? "простое" :
		       shm->verdict == V_COMPOSITE ? "составное" : "ни то, ни другое");
		atomic_store(&shm->state, ST_DONE);
	}

	printf("Первая программа завершила работу\n");
	if (shmdt(shm) == -1) {
		perror("shmdt");
		return 1;
	}
	return 0;
}
