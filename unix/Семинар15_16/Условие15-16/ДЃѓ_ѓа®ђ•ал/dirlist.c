/*
 * Упрощённый ls текущего каталога.
 * Скрытые имена (первый символ '.') пропускаются.
 * Для каждого файла печатаются тип, права rwx, число ссылок,
 * владелец, группа, размер и имя.
 *
 * Программа в таком виде некорректна: nuser и ngroup — неинициализированные
 * указатели. В ветке else sprintf пишет по случайному адресу.
 * Перед sprintf для числового uid/gid нужна своя строка-буфер.
 * opendir и lstat тоже не проверяются.
 */

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <dirent.h>
#include <stdio.h>
#include <fcntl.h>
#include <pwd.h>
#include <grp.h>
main()
{
 DIR *D;
 struct dirent *de;
 struct stat st;
 struct passwd *pwd;
 struct group *grp;
 int mode,right_ind;
 static char* rights = "rwxrwxrwx"; /* девять бит: владелец, группа, остальные */
 char *nuser,*ngroup;
 D = opendir(".");
 while( de = readdir(D) )
 {
    if( de->d_name[0] != '.' )
    {
	/* lstat не идёт по символической ссылке, в отличие от stat. */
	lstat(de->d_name,&st);
	mode = st.st_mode;
	S_ISDIR(mode)?printf("d"):printf("-");
	mode &= 0777;          /* оставить только 9 бит прав */
	right_ind = 0;
	while( right_ind < 9 )
	{
	    /* 256 — это бит 8, старший из девяти. Сдвиг двигает следующий бит на его место. */
	    mode&256?printf("%c",rights[right_ind]):printf("-");
	    mode <<= 1;
	    right_ind++;
	}
	if (pwd=getpwuid(st.st_uid)) nuser=pwd->pw_name; 
	else sprintf(nuser,"%d",st.st_uid);
	if (grp=getgrgid(st.st_gid)) ngroup=grp->gr_name; 
	else sprintf(ngroup,"%d",st.st_gid);
	
	printf("%3d %s\t%s %8d %s\n",st.st_nlink,nuser,ngroup,st.st_size,de->d_name);
    }
 }
 closedir(D);
}
