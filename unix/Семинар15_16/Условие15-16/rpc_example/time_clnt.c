/*
 * Клиент службы RDATE.
 * Спрашивает у сервера текущее время числом, затем просит строку для этого числа
 * и печатает её. Сервер должен уже быть запущен (./time_svc).
 */

#include <stdio.h>
#include <time.h>

#include <rpc/rpc.h>
#include "rdate.h"
#define RMACHINE "localhost"

CLIENT *handle;

long bin_date(void)
{
	long *p;
	/*
	 * bin_date_1 уже возвращает long *. Знак & здесь лишний:
	 * берётся адрес временного указателя, такой код современный компилятор
	 * не собирает. Нужно писать p = bin_date_1(NULL, handle).
	 * NULL — потому что у процедуры нет аргумента.
	 */
	p = &bin_date_1(NULL, handle);
	return *p;
}

char *str_date(long t)
{
	char **p;

	/* str_date_1 возвращает char **: указатель на строку в static-буфере заглушки. */
	p = str_date_1(&t, handle);
	return *p;
}

int main(int argc, char **argv)
{
	long t;
	char *str;

	(void)argc;
	(void)argv;

	/* Найти программу RDATE_PROG версии RDATE_VERS на localhost по TCP. */
	handle = clnt_create(RMACHINE, RDATE_PROG, RDATE_VERS, "tcp");
	if (handle == NULL)
	{
		clnt_pcreateerror( RMACHINE );
		perror("clnt_create failed");
		exit(1);
	}

	t = bin_date();
	str = str_date(t);

	puts(str);
	exit(0);
}
