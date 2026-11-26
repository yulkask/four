/*
 * Процедуры сервера RDATE.
 * main() и приём запросов лежат в rdate_svc.c, его пишет rpcgen.
 * Здесь только то, что вызывается, когда приходит запрос клиента.
 * Результаты static: каркас сервера читает их уже после return.
 */

#include <stdio.h>
#include <time.h>

#include <rpc/rpc.h>
#include "rdate.h"

/* Секунды с 1 января 1970 года, UTC. */
long bin_date(void)
{
	return (long) time(NULL);
}

/* ctime дописывает '\n' в конец строки. Буфер внутри ctime статический. */
char *str_date(long t)
{
	return ctime((time_t *) &t);
}

/* Обёртка версии 1: имя bin_date_1_svc задаёт rpcgen. */
long *bin_date_1_svc(void *p, struct svc_req *cl)
{
	static long t;

	(void)p;
	(void)cl;
	t = bin_date();
	return &t;
}

char **str_date_1_svc(long *t, struct svc_req *cl)
{
	static char *s;

	(void)cl;
	s = str_date(*t);
	return &s;
}
