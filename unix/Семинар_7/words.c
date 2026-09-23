/*
 * Чтение строк из текстового файла, выделение слов регулярным
 * выражением \b\w+\b и вывод их через точку.
 *
 * Использование: ./words файл      (без аргумента читается stdin)
 */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE   /* иначе macOS скрывает REG_ENHANCED */
#include <locale.h>
#include <regex.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* На macOS \w и \b работают только с флагом REG_ENHANCED,
   в glibc (Linux) они поддерживаются и так. */
#ifndef REG_ENHANCED
#define REG_ENHANCED 0
#endif

#define WORD_RE "\\b\\w+\\b"

/* Печатает слова строки через точку, возвращает их количество */
static int print_words(const regex_t *preg, const char *line)
{
    regmatch_t pm;
    const char *p = line;
    int count = 0;
    int eflags = 0;

    while (regexec(preg, p, 1, &pm, eflags) == 0) {
        if (count > 0)
            putchar('.');
        printf("%.*s", (int)(pm.rm_eo - pm.rm_so), p + pm.rm_so);
        count++;

        p += pm.rm_eo;
        /* Поиск продолжается с середины строки: это уже не её начало */
        eflags = REG_NOTBOL;
    }
    if (count > 0)
        putchar('\n');
    return count;
}

int main(int argc, char *argv[])
{
    FILE *fp = stdin;
    regex_t preg;
    char *line = NULL;
    size_t cap = 0;
    int rc, total = 0;

    /* Локаль из окружения, чтобы \w распознавал кириллицу в UTF-8 */
    setlocale(LC_ALL, "");

    if (argc > 2) {
        fprintf(stderr, "Использование: %s [файл]\n", argv[0]);
        return 1;
    }
    if (argc == 2 && (fp = fopen(argv[1], "r")) == NULL) {
        perror(argv[1]);
        return 1;
    }

    rc = regcomp(&preg, WORD_RE, REG_EXTENDED | REG_ENHANCED);
    if (rc != 0) {
        char err[256];
        regerror(rc, &preg, err, sizeof err);
        fprintf(stderr, "regcomp: %s\n", err);
        return 1;
    }

    while (getline(&line, &cap, fp) != -1)
        total += print_words(&preg, line);

    printf("Всего слов: %d\n", total);

    free(line);
    regfree(&preg);
    if (fp != stdin)
        fclose(fp);
    return 0;
}
