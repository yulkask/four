/* ЗАПУСК
cd unix/Семинар1_2
cc functions.c -o functions -Wno-deprecated-declarations
./functions */

#include <fcntl.h> 
#include <unistd.h>  
#include <string.h>  

#define BUFSIZE 1024

static void print_msg(const char *s)
{
    write(1, s, strlen(s));
}

int main(void)
{
    int  fd;             /* дескриптор файла */
    char buf[BUFSIZE];   /* буфер для данных */
    int  len;            /* количество прочитанных байт */

    const char *filename = "myfile.txt";
    fd = creat(filename, 0644);
    if (fd < 0) {
        write(2, "Ошибка: creat() не выполнен\n", 29);
        return 1;
    }

    print_msg("Введите строки:\n");

    while (1) {
        len = read(0, buf, sizeof(buf));

        if (len <= 0) break;                    

        if (len == 1 && buf[0] == '\n')
            break;

        write(fd, buf, len);
    }

    close(fd);

    fd = open(filename, O_RDONLY);
    if (fd < 0) {
        write(2, "Ошибка: open() не выполнен\n", 28);
        return 1;
    }

    print_msg("\n Содержимое файла \n");

    while ((len = read(fd, buf, sizeof(buf))) > 0) {
        write(1, buf, len);
    }

    close(fd);   /* закрыть файл после чтения */

    return 0;
}