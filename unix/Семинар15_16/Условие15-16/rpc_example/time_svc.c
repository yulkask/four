#include <stdio.h>
#include <time.h>

#include <rpc/rpc.h>
#include "rdate.h"

long bin_date(void)
{
	return (long) time(NULL);
}

char *str_date(long t)
{
	return ctime((time_t *) &t);
}

long *bin_date_1_svc(void *p, struct svc_req *cl)
{
	static long t;

	t = bin_date();
	return &t;
}

char **str_date_1_svc(long *t, struct svc_req *cl)
{
	static char *s;

	s = str_date(*t);
	return &s;
}
