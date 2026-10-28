#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <ucontext.h>

// 4096 байт из примера в man мало: printf на macOS требует больший стек
#define STACK_SIZE (64 * 1024)

#define handle_error(msg) do { perror(msg); exit(EXIT_FAILURE); } while (0)

static ucontext_t uctx_main, uctx_power, uctx_fact;

// Аргументы и результаты: makecontext передаёт функциям только int,
// поэтому X и результаты (double) лежат в глобальных переменных
static double x;
static double power_result, fact_result;

// Функции, которые будут выполняться в отдельных контекстах
static void power(int n)
{
	printf("power: started, считаем (%g)^%d\n", x, n); 
	double r = 1.0;
	for (int i = 0; i < n; i++) 
		r *= x;
	power_result = r;
	printf("power: готово, возврат в main через uc_link\n");
}

// Функция, которая будет выполняться в отдельном контексте
static void factorial(int n)
{
	printf("factorial: started, считаем %d!\n", n);
	double r = 1.0;
	for (int i = 2; i <= n; i++)
		r *= i;
	fact_result = r;
	printf("factorial: готово, возврат в main через uc_link\n");
}

// Готовит контекст: свой стек, возврат в main после завершения функции.
static void make_ctx(ucontext_t *ctx, char *stack, void (*func)(int), int n)
{
	if (getcontext(ctx) == -1) // заполняем структуру текущем состосянием
		handle_error("getcontext"); 
	ctx->uc_stack.ss_sp = stack;
	ctx->uc_stack.ss_size = STACK_SIZE;
	ctx->uc_link = &uctx_main; // при завершении функции передаем переход в main
	makecontext(ctx, (void (*)(void))func, 1, n);
}

// Читает аргументы командной строки, проверяет их и возвращает в n
static int read_args(int argc, char *argv[], int *n)
{
	char *end;
	long v;

	if (argc != 3) {
		fprintf(stderr, "Использование: %s X N   (N — целое, 0 <= N <= 170)\n", argv[0]);
		return -1;
	}
	errno = 0;
	x = strtod(argv[1], &end);
	if (errno || end == argv[1] || *end) {
		fprintf(stderr, "X должно быть числом: %s\n", argv[1]);
		return -1;
	}
	errno = 0;
	v = strtol(argv[2], &end, 10);
	// 170! — наибольший факториал, который помещается в double.
	if (errno || end == argv[2] || *end || v < 0 || v > 170) {
		fprintf(stderr, "N должно быть целым от 0 до 170: %s\n", argv[2]);
		return -1;
	}
	*n = (int)v;
	return 0;
}

int main(int argc, char *argv[])
{
	static char power_stack[STACK_SIZE];
	static char fact_stack[STACK_SIZE];
	int n;

	if (read_args(argc, argv, &n) == -1)
		return EXIT_FAILURE;

	make_ctx(&uctx_power, power_stack, power, n);
	make_ctx(&uctx_fact, fact_stack, factorial, n);

	printf("main: swapcontext(&uctx_main, &uctx_power)\n");
	if (swapcontext(&uctx_main, &uctx_power) == -1)
		handle_error("swapcontext");
	printf("main: вернулись из power, X^N = %g\n", power_result);

	printf("main: swapcontext(&uctx_main, &uctx_fact)\n");
	if (swapcontext(&uctx_main, &uctx_fact) == -1)
		handle_error("swapcontext");
	printf("main: вернулись из factorial, N! = %.0f\n", fact_result);

	printf("\n(%g)^%d / %d! = %g / %.0f = %.10g\n",
	       x, n, n, power_result, fact_result, power_result / fact_result);
	return EXIT_SUCCESS;
}
