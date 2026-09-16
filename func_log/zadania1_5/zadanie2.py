#нефункциональный

def collatz_imperative(n):
    sequence = [n]          # изменяемое состояние
    while n != 1:
        if n % 2 == 0:
            n = n // 2       # мутация переменной
        else:
            n = n * 3 + 1
        sequence.append(n)   # мутация списка
    return sequence


if __name__ == "__main__":
    n = int(input("Введите положительное целое число n: "))
    print(collatz_imperative(n))

    
#функциональный

def collatz_functional(n):
    def step(x):
        # чистая функция: результат зависит только от аргумента
        return x // 2 if x % 2 == 0 else x * 3 + 1

    def go(x, acc):
        # рекурсия вместо цикла, иммутабельное расширение списка
        if x == 1:
            return acc
        next_x = step(x)
        return go(next_x, acc + [next_x])

    return go(n, [n])


if __name__ == "__main__":
    n = int(input("Введите положительное целое число n: "))
    print(collatz_functional(n))
