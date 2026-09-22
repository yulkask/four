CXX := c++
CXXFLAGS := -std=c++17 -Wall -Wextra -Wpedantic

.PHONY: all clean

all: server client

server: server.cpp
	$(CXX) $(CXXFLAGS) $< -o $@

client: client.cpp
	$(CXX) $(CXXFLAGS) $< -o $@

clean:
	rm -f server client
