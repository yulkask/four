/*
 * Аналог stat для одного пути из argv[1].
 * Печатает тип, права, inode, число ссылок, устройство, владельца,
 * размер и три времени: доступ, модификация, смена статуса.
 * lstat смотрит на саму ссылку, не на файл, на который она указывает.
 * Аргумент и результат lstat не проверяются: без имени файла программа упадёт.
 */

#include <sys/types.h> 
#include <sys/stat.h>
#include <time.h>

main (int argc, char *argv[]) {
 struct stat s;
 char *ptype;
 lstat(argv[1],&s);
 
 /* st_mode хранит и тип файла, и права. Макросы S_IS* смотрят только тип. */
 if (S_ISREG(s.st_mode)) ptype="Standard file";
 else if (S_ISDIR(s.st_mode)) ptype="Catalogue";
 else if (S_ISLNK(s.st_mode)) ptype="SymLink"; 
 else if (S_ISCHR(s.st_mode)) ptype="Symb Device";
 else if (S_ISBLK(s.st_mode)) ptype="Block Device";
 else if (S_ISSOCK(s.st_mode)) ptype="Socket"; 
 else if (S_ISFIFO(s.st_mode)) ptype="Fifo";
 else ptype="Unknown";
 
 printf("type=%s\n",ptype);
 printf("perm=%o\n",s.st_mode); /* %o — восьмеричный вид, как в chmod */
 printf("inode=%d\n",s.st_ino);
 printf("nlink=%d\n",s.st_nlink);
 printf("dev=(%d,%d)\n",major(s.st_dev),minor(s.st_dev));
 printf("UID=%d\n",s.st_uid);
 printf("GID=%d\n",s.st_gid);
 /* Для устройства rdev — номер самого устройства, для обычного файла нули. */
 printf("rdev=(%d,%d)\n",major(s.st_rdev),minor(s.st_rdev));
 printf("size=%d\n",s.st_size);
 printf("atime=%s\n",ctime(&s.st_atime));
 printf("mtime=%s\n",ctime(&s.st_mtime));
 printf("ctime=%s\n",ctime(&s.st_ctime));
 _exit(0);
}
