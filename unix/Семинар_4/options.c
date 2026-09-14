#include <errno.h>
#include <getopt.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>


static void print_help(const char *program)
{
    printf("Использование:\n");
    printf("  %s -+ A B       %s --add A B\n", program, program); // A + B
    printf("  %s -n A B       %s --sub A B\n", program, program); // A - B
    printf("  %s -/ A B       %s --div A B\n", program, program); // A / B
    printf("  %s -* A B       %s --mul A B\n", program, program); // A * B
    printf("  %s -%% A B       %s --percent A B\n", program, program); // A %% от B
    printf("  %s -s A         %s --sqrt A\n\n", program, program); // корень из A
    printf("percent вычисляет A %% от B (A * B / 100).\n"); 
    printf("Можно использовать и форму --add=A B. За один запуск выбирается одна операция.\n");
}

static int read_number(const char *text, double *number)
{
    char *end;

    errno = 0;
    *number = strtod(text, &end);
    return errno == 0 && end != text && *end == '\0' && isfinite(*number);
}

static int get_second_number(int argc, char *argv[], double *number)
{
    if (optind >= argc) {
        fprintf(stderr, "Ошибка: для операции нужны два числа.\n");
        return 0;
    }
    if (!read_number(argv[optind++], number)) {
        fprintf(stderr, "Ошибка: \"%s\" не является числом.\n", argv[optind - 1]);
        return 0;
    }
    return 1;
}

int main(int argc, char *argv[])
{
    static const struct option long_options[] = {
        {"add", required_argument, NULL, '+'},
        {"sub", required_argument, NULL, 'n'},
        {"div", required_argument, NULL, '/'},
        {"mul", required_argument, NULL, '*'},
        {"percent", required_argument, NULL, '%'},
        {"sqrt", required_argument, NULL, 's'},
        {"help", no_argument, NULL, 'h'},
        {NULL, 0, NULL, 0}
    };
    int option;
    int operation = 0;
    double first;
    double second;
    double result;

    opterr = 0;
    while ((option = getopt_long(argc, argv, "+:n:/:*:%:s:h", long_options,
                                 NULL)) != -1) {
        if (option == 'h') {
            print_help(argv[0]);
            return EXIT_SUCCESS;
        }
        if (option == '?' || option == ':') {
            fprintf(stderr, "Ошибка: неизвестная опция или отсутствует её аргумент.\n");
            print_help(argv[0]);
            return EXIT_FAILURE;
        }
        if (operation != 0) {
            fprintf(stderr, "Ошибка: укажите только одну операцию.\n");
            return EXIT_FAILURE;
        }
        if (!read_number(optarg, &first)) {
            fprintf(stderr, "Ошибка: \"%s\" не является числом.\n", optarg);
            return EXIT_FAILURE;
        }
        operation = option;
        if (operation != 's' && !get_second_number(argc, argv, &second))
            return EXIT_FAILURE;
    }

    if (operation == 0) {
        fprintf(stderr, "Ошибка: операция не задана.\n");
        print_help(argv[0]);
        return EXIT_FAILURE;
    }
    if (optind != argc) {
        fprintf(stderr, "Ошибка: лишний аргумент \"%s\".\n", argv[optind]);
        return EXIT_FAILURE;
    }

    switch (operation) {
    case '+': result = first + second; break;
    case 'n': result = first - second; break;
    case '/':
        if (second == 0.0) {
            fprintf(stderr, "Ошибка: деление на ноль.\n");
            return EXIT_FAILURE;
        }
        result = first / second;
        break;
    case '*': result = first * second; break;
    case '%': result = first * second / 100.0; break;
    case 's':
        if (first < 0.0) {
            fprintf(stderr, "Ошибка: нельзя извлечь квадратный корень из отрицательного числа.\n");
            return EXIT_FAILURE;
        }
        result = sqrt(first);
        break;
    default:
        return EXIT_FAILURE;
    }

    printf("Результат: %.10g\n", result);
    return EXIT_SUCCESS;
}
