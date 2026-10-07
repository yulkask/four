CC = cc
CFLAGS = -std=gnu11 -Wall -Wextra -pedantic -O2
LDLIBS = -lm

PROGRAMS = normal

all: $(PROGRAMS)

normal: normal.c
	$(CC) $(CFLAGS) $< -o $@ $(LDLIBS)

clean:
	rm -f $(PROGRAMS)

.PHONY: all clean
