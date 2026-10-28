# Семинар 13: переключение контекста (`ucontext.h`)

- `context_example_man.c` — пример из `man makecontext`;
- `power_fact.c` — задание на оценку: X^N и N! считаются в отдельных
  контекстах, затем X^N делится на N!.

Сборка и запуск (из этой папки):

```sh
cd unix/Семинар_13
make
./context_example_man       # uc_link у func2 = &uctx_func1
./context_example_man x     # uc_link у func2 = NULL
./power_fact 2 10           # X = 2, N = 10
```

На macOS `ucontext.h` подключается только с `-D_XOPEN_SOURCE=600`, а сами
функции помечены устаревшими. Поэтому в `Makefile` предупреждения об этом
отключены. На Linux программы собираются так же.

## Функции

| Функция | Что делает |
|---|---|
| `getcontext(&ctx)` | сохраняет в `ctx` текущий контекст: регистры, указатель стека, маску сигналов |
| `makecontext(&ctx, f, argc, ...)` | меняет контекст из `getcontext` так, чтобы при переходе в него вызвалась `f(...)` на стеке `ctx.uc_stack`. Аргументы могут быть только `int`. Когда `f` завершится, произойдёт переход в `ctx.uc_link`. Если `uc_link == NULL`, завершится поток |
| `swapcontext(&old, &new)` | сохраняет текущий контекст в `old` и переходит в `new`. Возврат из `swapcontext` случится, когда кто-то перейдёт обратно в `old` |

## Пример из man: почему такой результат

```
$ ./context_example_man
main: swapcontext(&uctx_main, &uctx_func2)
func2: started
func2: swapcontext(&uctx_func2, &uctx_func1)
func1: started
func1: swapcontext(&uctx_func1, &uctx_func2)
func2: returning
func1: returning
main: exiting
```

1. `main` сохраняет себя в `uctx_main` и переходит в `func2`. Сначала
   вызывается `func2`, хотя `func1` подготовлена первой: порядок задаётся
   переключениями, а не порядком `makecontext`.
2. `func2` сохраняет себя в `uctx_func2` и переходит в `func1`, которая
   стартует с начала.
3. `func1` сохраняет себя в `uctx_func1` и переходит в `uctx_func2`. Это
   уже не начало `func2`, а точка внутри её `swapcontext`. Поэтому `func2`
   продолжает работу и печатает `returning`.
4. `func2` завершается. Её `uc_link = &uctx_func1`, поэтому управление
   переходит в точку, где остановилась `func1`, и та печатает `returning`.
5. `func1` завершается. Её `uc_link = &uctx_main`, поэтому выполнение
   продолжается в `main` после `swapcontext`, и `main` печатает `exiting`.

Функции работают как сопрограммы: каждая `swapcontext` замораживает текущую
функцию вместе с её стеком, и потом функция продолжается с того же места.
Стеки у `func1` и `func2` свои (`func1_stack`, `func2_stack`), поэтому
локальные данные приостановленной функции не портятся.

С аргументом (`./context_example_man x`) у `func2` `uc_link = NULL`:

```
main: swapcontext(&uctx_main, &uctx_func2)
func2: started
func2: swapcontext(&uctx_func2, &uctx_func1)
func1: started
func1: swapcontext(&uctx_func1, &uctx_func2)
func2: returning
```

После `func2: returning` переходить некуда, и поток (здесь он единственный)
завершается. Процесс выходит с кодом 0, а `func1: returning` и
`main: exiting` не печатаются. Если вывод направлен в канал или файл
(`./context_example_man x | cat`), не печатается вообще ничего: процесс
завершается без `exit()`, и буфер `stdout` не сбрасывается.

## Задание: X^N / N!

Схема такая же, как в примере, но оба контекста возвращаются в `main`:

```
main ──swapcontext──▶ power(N)      ──uc_link──▶ main
main ──swapcontext──▶ factorial(N)  ──uc_link──▶ main
main: power_result / fact_result
```

- У обоих контекстов `uc_link = &uctx_main`. Когда функция завершается,
  `main` продолжает работу после своего `swapcontext`.
- N передаётся через `makecontext(ctx, func, 1, n)`. `makecontext` принимает
  только аргументы типа `int`, поэтому X (`double`) и результаты лежат
  в глобальных переменных.
- Стеки по 64 КБ и объявлены `static`. 4096 байт из примера в man мало:
  на macOS `printf` использует больше стека, и программа может упасть.
- Значения считаются в `double`. Так N может быть до 170: 170! ≈ 7,3·10³⁰⁶,
  а 171! уже не помещается в `double`. Ввод проверяется через
  `strtod`/`strtol`.

Пример:

```
$ ./power_fact 2 10
main: swapcontext(&uctx_main, &uctx_power)
power: started, считаем (2)^10
power: готово, возврат в main через uc_link
main: вернулись из power, X^N = 1024
main: swapcontext(&uctx_main, &uctx_fact)
factorial: started, считаем 10!
factorial: готово, возврат в main через uc_link
main: вернулись из factorial, N! = 3628800

(2)^10 / 10! = 1024 / 3628800 = 0.0002821869489

$ ./power_fact 3 5 | tail -1
(3)^5 / 5! = 243 / 120 = 2.025

$ ./power_fact 2 171
N должно быть целым от 0 до 170: 171
```
