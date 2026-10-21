#ifndef COMMON_H
#define COMMON_H

#include <sys/types.h>
#include <sys/ipc.h>

/* Ключ очереди обе программы получают одинаково: ftok от одного и того же
 * файла. В примере был жёсткий ключ 666, он мог совпасть с чужой очередью. */
#define KEY_FILE "common.h"
#define KEY_PROJ 'Q'

/* Тип сообщения-запроса. Ответ отправляется с типом, равным pid первой
 * программы, поэтому каждая из нескольких запущенных ask получает только
 * свой ответ. pid всегда больше 1, так что с запросом он не совпадёт. */
#define MT_REQUEST 1

// Результат проверки числа.
enum verdict {
	V_NONE = 0,  // 0 и 1 не простые и не составные
	V_PRIME,
	V_COMPOSITE
};

// Сообщение: запрос (ask -> check) и ответ (check -> ask).
struct message {
	long mtype;               // MT_REQUEST или pid получателя ответа
	pid_t pid;                // кто спрашивает (в запросе)
	unsigned long long value; // проверяемое число
	int verdict;              // enum verdict (в ответе)
};

// Размер полезной части сообщения: всё, кроме mtype.
#define MSG_SIZE (sizeof(struct message) - sizeof(long))

#endif
