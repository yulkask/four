CC = cc
CFLAGS = -std=c11 -Wall -Wextra -pedantic

PROGRAMS = regex words

all: $(PROGRAMS)

# Исходный пример собирается без -pedantic, чтобы не менять его код
regex: regex.c
	$(CC) $< -o $@

words: words.c
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -f $(PROGRAMS)

.PHONY: all clean
