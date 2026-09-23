#define _POSIX_C_SOURCE 200809L

#include <dirent.h>
#include <errno.h>
#include <grp.h>
#include <inttypes.h>
#include <limits.h>
#include <pwd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static void print_permissions(mode_t mode)
{
    const char symbols[] = "rwxrwxrwx";
    int bit;

    putchar(S_ISDIR(mode) ? 'd' : S_ISLNK(mode) ? 'l' : '-');
    for (bit = 8; bit >= 0; --bit)
        putchar((mode & (1u << bit)) ? symbols[8 - bit] : '-');
}

static int make_path(char *result, size_t result_size, const char *directory,
                     const char *name)
{
    int has_trailing_slash = directory[0] != '\0' &&
                             directory[strlen(directory) - 1] == '/';
    int written = snprintf(result, result_size, "%s%s%s", directory,
                           has_trailing_slash ? "" : "/", name);
    return written >= 0 && (size_t)written < result_size;
}

static void print_entry(const char *directory, const char *name)
{
    char path[PATH_MAX];
    struct stat info;
    struct passwd *user;
    struct group *group;

    if (!make_path(path, sizeof(path), directory, name)) {
        fprintf(stderr, "Слишком длинный путь: %s/%s\n", directory, name);
        return;
    }
    if (lstat(path, &info) == -1) {
        fprintf(stderr, "Не удалось получить сведения о %s: %s\n", path,
                strerror(errno));
        return;
    }

    user = getpwuid(info.st_uid);
    group = getgrgid(info.st_gid);
    print_permissions(info.st_mode);
    printf(" %3ju %-8s %-8s %8jd %s", (uintmax_t)info.st_nlink,
           user ? user->pw_name : "?", group ? group->gr_name : "?",
           (intmax_t)info.st_size, name);

    if (S_ISLNK(info.st_mode)) {
        char target[PATH_MAX];
        ssize_t length = readlink(path, target, sizeof(target) - 1);

        if (length >= 0) {
            target[length] = '\0';
            printf(" -> %s", target);
        }
    }
    putchar('\n');
}

int main(int argc, char *argv[])
{
    const char *directory = argc == 2 ? argv[1] : ".";
    DIR *stream;
    struct dirent *entry;

    if (argc > 2) {
        fprintf(stderr, "Использование: %s [каталог]\n", argv[0]);
        return EXIT_FAILURE;
    }

    stream = opendir(directory);
    if (stream == NULL) {
        fprintf(stderr, "Не удалось открыть каталог %s: %s\n", directory,
                strerror(errno));
        return EXIT_FAILURE;
    }

    errno = 0;
    while ((entry = readdir(stream)) != NULL) {
        if (entry->d_name[0] != '.')
            print_entry(directory, entry->d_name);
    }
    if (errno != 0) {
        fprintf(stderr, "Ошибка чтения каталога %s: %s\n", directory,
                strerror(errno));
        closedir(stream);
        return EXIT_FAILURE;
    }
    if (closedir(stream) == -1) {
        fprintf(stderr, "Не удалось закрыть каталог %s: %s\n", directory,
                strerror(errno));
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
