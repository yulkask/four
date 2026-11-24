#include <stdio.h>
#include <time.h>

#include <rpc/rpc.h>
#include "rdate.h"
#define RMACHINE "localhost"

CLIENT *handle;

long bin_date(void)
{
	long *p;
	p = &bin_date_1(NULL, handle);
	return *p;
}

char *str_date(long t)
{
	char **p;

	p = str_date_1(&t, handle);
	return *p;
}

int main(int argc, char **argv)
{
	long t;
	char *str;

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
