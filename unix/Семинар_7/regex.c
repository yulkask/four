#include <regex.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define BUF_SIZE 256

/* На macOS \w и \b работают только с флагом REG_ENHANCED,
   в glibc (Linux) они поддерживаются и так. */
#ifndef REG_ENHANCED
#define REG_ENHANCED 0
#endif

char* paste_env(char *str)
{
    char *env;
    char buf[BUF_SIZE];
    regex_t preg;
    regmatch_t pm;
    char *newstr, *ptr = NULL;
    int len;

    regcomp( &preg, "\\$\\w+", REG_EXTENDED | REG_ENHANCED); //REG_ICASE | 
    int i;
    int offset = 0;
    while (regexec(&preg, str+offset, 1, &pm, REG_NOTBOL) == 0)
    {
	if(pm.rm_so == -1) continue;
	int so = pm.rm_so+offset;
	int eo = pm.rm_eo+offset;
	memset(buf, '\0', BUF_SIZE);
	strncpy(buf,&str[so]+1,(eo-so-1 < BUF_SIZE)?eo-so-1:BUF_SIZE-1);

	printf("match: %s, rm_so=%d, rm_eo=%d\n",buf,so,eo);

	env = getenv(buf);
	if(env)
	{
		len = strlen(str)-strlen(buf)+strlen(env);
		newstr=malloc(len);
		memset(newstr, 0, len);
		strncpy(newstr,str,so);
		strncat(newstr,env,strlen(env));
		strncat(newstr,&str[eo],strlen(str)-eo);
		str = newstr;
		if(ptr) free(ptr);
		ptr = newstr;
		offset += strlen(buf);
	}
	else offset += pm.rm_eo;
    }
    regfree(&preg);

    return str;
}


int main ()
{
    printf("%s\n","SOURCE STRING: $HOME something... $PWD $TERM");
    printf("%s\n",paste_env("FINAL STRING: $HOME something... $PWD $TERM"));

    return 0;
}
