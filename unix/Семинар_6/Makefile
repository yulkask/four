CC = cc
# На macOS S-Lang ставится через Homebrew: brew install s-lang
SLANG_PREFIX ?= $(shell brew --prefix s-lang 2>/dev/null || echo /usr)
CFLAGS = -std=gnu11 -Wall -Wextra -pedantic -I$(SLANG_PREFIX)/include
LDLIBS = -L$(SLANG_PREFIX)/lib -lslang

PROGRAMS = slang slang_file

all: $(PROGRAMS)

slang: slang.c
	$(CC) -I$(SLANG_PREFIX)/include $< -o $@ $(LDLIBS)

slang_file: slang_file.c
	$(CC) $(CFLAGS) $< -o $@ $(LDLIBS)

clean:
	rm -f $(PROGRAMS)

.PHONY: all clean
