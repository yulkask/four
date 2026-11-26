/*
 * Учебный аналог chown.
 * Три аргумента:  программа пользователь файл
 *   владелец и группа файла становятся uid и основной группой этого пользователя.
 * Четыре аргумента: программа группа пользователь файл
 *   (порядок группы и пользователя здесь обратный привычному chown user:group).
 * Имена переводятся в числовые id через getpwnam и getgrnam.
 * chown меняет владельца по пути; для ссылки понадобился бы lchown.
 * Заголовок sys/sysinfo.h к смене владельца не относится и на macOS отсутствует.
 */

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
	/* Фактически argv[1] — группа, argv[2] — пользователь, argv[3] — файл. */
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
