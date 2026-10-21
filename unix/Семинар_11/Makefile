CC = cc
CFLAGS = -std=gnu11 -Wall -Wextra -pedantic -O2

PROGRAMS = ask check

all: $(PROGRAMS)

ask: ask.c common.h
	$(CC) $(CFLAGS) ask.c -o $@

check: check.c common.h
	$(CC) $(CFLAGS) check.c -o $@

clean:
	rm -f $(PROGRAMS)

.PHONY: all clean
