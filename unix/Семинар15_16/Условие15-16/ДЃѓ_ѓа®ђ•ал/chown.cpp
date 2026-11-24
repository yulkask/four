#include <stdio.h>
#include <string.h>
#include <sys/sysinfo.h>
#include <sys/types.h>
#include <unistd.h>
#include <grp.h>
#include <pwd.h>

int main(int argc, char * argv[])
{
    struct passwd * userinfo = NULL;
    struct group * grinfo = NULL;
    if (argc == 3) // command, user, file(folder)
    {
	userinfo = getpwnam(argv[1]);
	if (userinfo != NULL)
	{
	    if (chown(argv[2], userinfo->pw_uid, userinfo->pw_gid) == -1)
	    {
		printf("Error!!! File name wrong of no permission!\n");
		return 0;
	    }
	    else
	    {
		printf("Changed\n");
	    }
	}
	else
	{
	    printf("Error!!! No such user!\n");
	    return 0;
	}
    }
    else if (argc == 4)//command , user, group,file(folder)
    {
	userinfo = getpwnam(argv[2]);
	grinfo = getgrnam(argv[1]);
	if ((userinfo != NULL) && (grinfo != NULL))
	{
	    if (chown(argv[3], userinfo->pw_uid, grinfo->gr_gid) == -1)
	    {
		printf("Error!!! File name wrong of no permission!\n");
		return 0;
	    }
	    else
	    {
		printf("Changed\n");
	    }
	}
	else
	{
	    printf("Error!!! No such group!\n");
	    return 0;
	}
    }
    else
    {
	printf("Error!!!Wrong number of parameters\n");
    }
    return 0;
}

