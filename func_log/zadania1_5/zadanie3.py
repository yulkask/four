#нефункциональный 

def histogram_imperative(numbers):
    lines = []                        # изменяемое состояние
    for n in numbers:                 # явный цикл
        bar = ""
        for _ in range(n):            # ещё один вложенный цикл
            bar += "#"                # мутация строки-аккумулятора
        lines.append(bar)             # мутация списка
    return lines


if __name__ == "__main__":
    data = input("Введите числа через пробел: ")
    numbers = [int(x) for x in data.split()]
    for line in histogram_imperative(numbers):
        print(line)


#функциональный

def histogram_functional(numbers):
    return ["#" * n for n in numbers]


if __name__ == "__main__":
    data = input("Введите числа через пробел: ")
    numbers = [int(x) for x in data.split()]
    print("\n".join(histogram_functional(numbers)))
