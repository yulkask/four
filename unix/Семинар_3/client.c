#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define DEFAULT_SERVER_FIFO "/tmp/fifo_server"

static char client_fifo[PATH_MAX];
static volatile sig_atomic_t finish = 0;

static void finish_client(int signal_number)
{
    (void)signal_number;
    finish = 1;
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

int main(int argc, char *argv[])
{
    const char *server_fifo = argc > 1 ? argv[1] : DEFAULT_SERVER_FIFO;
    int server_fd, client_fd;
    unsigned long long symbols = 0;
    char buffer[4096];
    char request[PATH_MAX + 2];
    struct timespec started, now;

    if (argc > 2) {
        fprintf(stderr, "Usage: %s [server_fifo_path]\n", argv[0]);
        return EXIT_FAILURE;
    }

    if (snprintf(client_fifo, sizeof(client_fifo), "/tmp/fifo_client_%ld", (long)getpid())
        >= (int)sizeof(client_fifo)) {
        fprintf(stderr, "client: FIFO path is too long\n");
        return EXIT_FAILURE;
    }

    umask(0);
    if (mkfifo(client_fifo, 0666) == -1) {
        perror("client: mkfifo");
        return EXIT_FAILURE;
    }

    /* A path plus '\n' is smaller than PIPE_BUF, so it is one atomic request. */
    server_fd = open(server_fifo, O_WRONLY);
    if (server_fd == -1) {
        perror("client: cannot connect to server FIFO");
        unlink(client_fifo);
        return EXIT_FAILURE;
    }
    if (snprintf(request, sizeof(request), "%s\n", client_fifo) >= (int)sizeof(request) ||
        write_all(server_fd, request, strlen(request)) == -1) {
        perror("client: send FIFO path");
        close(server_fd);
        unlink(client_fifo);
        return EXIT_FAILURE;
    }
    close(server_fd);

    /* This unblocks the server child, which opens our FIFO for writing. */
    client_fd = open(client_fifo, O_RDONLY);
    if (client_fd == -1) {
        perror("client: open own FIFO");
        unlink(client_fifo);
        return EXIT_FAILURE;
    }

    signal(SIGINT, finish_client);
    signal(SIGTERM, finish_client);
    clock_gettime(CLOCK_MONOTONIC, &started);

    while (!finish) {
        ssize_t received = read(client_fd, buffer, sizeof(buffer));
        if (received > 0) {
            symbols += (unsigned long long)received;
        } else if (received == 0) {
            break;
        } else if (errno != EINTR) {
            perror("client: read");
            break;
        }

        clock_gettime(CLOCK_MONOTONIC, &now);
        if (now.tv_sec - started.tv_sec >= 30)
            finish = 1;
    }

    close(client_fd);
    unlink(client_fifo);
    clock_gettime(CLOCK_MONOTONIC, &now);
    printf("Received %llu symbols in %ld seconds.\n", symbols,
           (long)(now.tv_sec - started.tv_sec));
    return EXIT_SUCCESS;
}
