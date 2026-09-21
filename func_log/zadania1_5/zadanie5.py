# нефункциональный

def max_identical_imperative(numbers):
    if not numbers:
        return None
    
    max_value = numbers[0]
    max_length = 1
    current_value = numbers[0]
    current_length = 1
    
    for i in range(1, len(numbers)):
        if numbers[i] == current_value:
            current_length += 1
        else:
            if current_length > max_length:
                max_length = current_length
                max_value = current_value
            current_value = numbers[i]
            current_length = 1
    
    # Проверка последней последовательности
    if current_length > max_length:
        max_length = current_length
        max_value = current_value
    
    return max_value


if __name__ == "__main__":
    data = input("Введите числа через пробел: ")
    numbers = [int(x) for x in data.split()]
    print(f"Входные данные: {numbers}")
    print(f"Максимальная идентичная последовательность: {max_identical_imperative(numbers)}")

    # функциональный

from itertools import groupby

def max_identical_functional_groupby(numbers):
    if not numbers:
        return None
    
    # Группируем одинаковые соседние значения
    groups = ((key, sum(1 for _ in group)) for key, group in groupby(numbers))
    
    # Находим группу с максимальной длиной (первая среди равных)
    max_group = max(groups, key=lambda x: x[1])
    
    return max_group[0]


if __name__ == "__main__":
    data = input("Введите числа через пробел: ")
    numbers = [int(x) for x in data.split()]
    print(f"Входные данные: {numbers}")
    print(f"Максимальная идентичная последовательность: {max_identical_functional_groupby(numbers)}")