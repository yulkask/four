CC = cc
CFLAGS = -std=c11 -Wall -Wextra -Wpedantic -O2

.PHONY: all clean

all: server client

server: server.c
	$(CC) $(CFLAGS) -o $@ $<

client: client.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f server client
