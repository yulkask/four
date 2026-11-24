#include <unistd.h>
#include <stdio.h>
#include <string.h>


bool s = false;
bool f = false;

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
	
    if (f)
	unlink(argv[argc-1]);
	
	
    if (result == -1)
    {
	printf("Error! Can't link %s to %s", argv[argc-2], argv[argc-1]);
	return -1;
    }
	
    return 0;
}
