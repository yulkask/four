/*
 * Пример разбора коротких опций через getopt (из man getopt).
 * Строка "abc:d:012" значит:
 *   a, b, 0, 1, 2 — флаги без аргумента;
 *   c и d — опции, которым обязателен аргумент (двоеточие после буквы).
 * Аргумент попадает в глобальную переменную optarg.
 * optind — индекс первого ещё не разобранного элемента argv.
 * Неизвестная опция даёт '?' ; getopt сам пишет сообщение в stderr.
 */

#include <stdio.h>     /* for printf */
#include <stdlib.h>    /* for exit */
#include <unistd.h>    /* for getopt */
int main (int argc, char **argv) {
    int c;
    int digit_optind = 0;
    int aopt = 0, bopt = 0;
    char *copt = 0, *dopt = 0;
    while ( (c = getopt(argc, argv, "abc:d:012")) != -1) {
        int this_option_optind = optind ? optind : 1;
        switch (c) {
        case '0':
        case '1':
        case '2':
            /* Цифры из двух разных слов argv считаются необычным случаем. */
            if (digit_optind != 0 && digit_optind != this_option_optind)
              printf ("digits occur in two different argv-elements.\n");
            digit_optind = this_option_optind;
            printf ("option %c\n", c);
            break;
        case 'a':
            printf ("option a\n");
            aopt = 1;
            break;
        case 'b':
            printf ("option b\n");
            bopt = 1;
            break;
        case 'c':
            printf ("option c with value '%s'\n", optarg);
            copt = optarg;
            break;
        case 'd':
            printf ("option d with value '%s'\n", optarg);
            dopt = optarg;
            break;
        case '?':
            break;
        default:
            printf ("?? getopt returned character code 0%o ??\n", c);
        }
    }
    /* Всё, что не является опцией, остаётся в argv начиная с optind. */
    if (optind < argc) {
        printf ("non-option ARGV-elements: ");
        while (optind < argc)
            printf ("%s ", argv[optind++]);
        printf ("\n");
    }
    (void)aopt;
    (void)bopt;
    (void)copt;
    (void)dopt;
    exit (0);
}
