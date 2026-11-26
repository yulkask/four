/*
 * Учебный аналог ln.
 * Последние два аргумента — существующий путь и новое имя ссылки.
 * Перед ними можно указать -s (символическая ссылка, symlink)
 * и -f (после создания ссылки новое имя сразу удаляется — так написано
 * в этом файле; обычный ln -f удаляет цель до создания ссылки).
 *
 * Файл написан как C, но использует bool без #include <stdbool.h>,
 * поэтому gcc его не собирает. Как C++ он тоже не соберётся без правки:
 * bool есть в C++, но прототипы link/symlink ожидают const char *.
 */

#include <unistd.h>
#include <stdio.h>
#include <string.h>


bool s = false; /* -s: symlink вместо жёсткой ссылки */
bool f = false; /* -f: unlink нового имени после link/symlink */

int main (int argc, char *argv[])
{
    if (argc < 3)
    {
	printf("Error! Gimme some more arguments!\n");
	return -1;
    }
    
    if (argv[1][0] == '-')
    {
	if (argc < 4)
	{
	    printf("Error! Gimme some more arguments!\n");
	    return -1;
	}
    
	/* Опции — все аргументы, кроме двух последних путей. */
	for (int i = 1; i < (argc-2); i++)
	{
	    switch(argv[i][1])
	    {
		case 's':
		    s = true;
		    break;
		case 'f':
		    f = true;
		    break;
	    }
	}
    }

    int result;
    
    if (s)
	result = symlink(argv[argc-2],argv[argc-1]);
    else
	result = link(argv[argc-2],argv[argc-1]);
	
    /* При -f новое имя удаляется сразу после создания. */
    if (f)
	unlink(argv[argc-1]);
	
	
    if (result == -1)
    {
	printf("Error! Can't link %s to %s", argv[argc-2], argv[argc-1]);
	return -1;
    }
	
    return 0;
}
