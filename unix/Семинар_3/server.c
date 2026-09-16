#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define DEFAULT_FIFO "/tmp/fifo_server"
#define PATH_BUFFER 1024

static const char *server_fifo;

static void stop_server(int signal_number)
{
    (void)signal_number;
    unlink(server_fifo);
    _exit(EXIT_SUCCESS);
}

static int write_all(int fd, const void *buffer, size_t count)
{
    const char *p = buffer;

    while (count > 0) {
        ssize_t written = write(fd, p, count);
        if (written > 0) {
            p += written;
            count -= (size_t)written;
        } else if (written == -1 && errno == EINTR) {
            continue;
        } else {
            return -1;
        }
    }
    return 0;
}

/* This function is run only in a child process, for one client. */
static void serve_client(const char *client_fifo)
{
    int client_fd = open(client_fifo, O_WRONLY);
    unsigned long sent = 0;
    unsigned int seed = (unsigned int)(time(NULL) ^ getpid());

    if (client_fd == -1) {
        perror("server: cannot open client FIFO");
        _exit(EXIT_FAILURE);
    }

    for (;;) {
        char symbol = (char)('A' + rand_r(&seed) % 26);

        if (write_all(client_fd, &symbol, 1) == -1) {
            /* The normal reason is that the client closed its FIFO. */
            break;
        }

        ++sent;
        if (sent % 1000 == 0 && rand_r(&seed) % 100 > 80) {
            /* A non-privileged process may not lower nice after raising it.
               This is normal on Unix, so a failed random attempt is ignored. */
            (void)setpriority(PRIO_PROCESS, getpid(), rand_r(&seed) % 11);
        }
    }

    close(client_fd);
    _exit(EXIT_SUCCESS);
}

int main(int argc, char *argv[])
{
    int server_fd;
    char buffer[4096];
    char pending[PATH_BUFFER];
    size_t pending_len = 0;

    server_fifo = argc > 1 ? argv[1] : DEFAULT_FIFO;
    if (argc > 2) {
        fprintf(stderr, "Usage: %s [server_fifo_path]\n", argv[0]);
        return EXIT_FAILURE;
    }

    umask(0);
    if (mkfifo(server_fifo, 0666) == -1 && errno != EEXIST) {
        perror("server: mkfifo");
        return EXIT_FAILURE;
    }

    /* O_RDWR keeps read() from returning EOF while no client is connected. */
    server_fd = open(server_fifo, O_RDWR);
    if (server_fd == -1) {
        perror("server: open FIFO");
        unlink(server_fifo);
        return EXIT_FAILURE;
    }

    signal(SIGCHLD, SIG_IGN);
    signal(SIGINT, stop_server);
    signal(SIGTERM, stop_server);
    printf("Server FIFO: %s\n", server_fifo);
    fflush(stdout);

    for (;;) {
        ssize_t received = read(server_fd, buffer, sizeof(buffer));
        size_t i;

        if (received == -1) {
            if (errno == EINTR)
                continue;
            perror("server: read");
            break;
        }

        for (i = 0; i < (size_t)received; ++i) {
            if (buffer[i] == '\n') {
                pid_t child;
                pending[pending_len] = '\0';
                if (pending_len == 0) {
                    continue;
                }
                child = fork();
                if (child == 0)
                    serve_client(pending);
                if (child == -1)
                    perror("server: fork");
                pending_len = 0;
            } else if (pending_len + 1 < sizeof(pending)) {
                pending[pending_len++] = buffer[i];
            } else {
                fprintf(stderr, "server: client FIFO path is too long\n");
                pending_len = 0;
            }
        }
    }

    close(server_fd);
    unlink(server_fifo);
    return EXIT_FAILURE;
}
