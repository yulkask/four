CC = cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic

PROGRAMS = dirlist dirlist_scandir

all: $(PROGRAMS)

dirlist: dirlist.c
	$(CC) $(CFLAGS) $< -o $@

dirlist_scandir: dirlist_scandir.c
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -f $(PROGRAMS)

.PHONY: all clean
