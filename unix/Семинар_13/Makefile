CC = cc
# _XOPEN_SOURCE нужен для ucontext.h на macOS; там эти функции помечены
# устаревшими, поэтому предупреждения об этом отключены.
CFLAGS = -std=gnu11 -Wall -Wextra -pedantic -O2 -D_XOPEN_SOURCE=600 -Wno-deprecated-declarations

PROGRAMS = context_example_man power_fact

all: $(PROGRAMS)

context_example_man: context_example_man.c
	$(CC) $(CFLAGS) -Wno-unused-parameter context_example_man.c -o $@

power_fact: power_fact.c
	$(CC) $(CFLAGS) power_fact.c -o $@

clean:
	rm -f $(PROGRAMS)

.PHONY: all clean
