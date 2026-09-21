# нефункциональный

def find_missing_imperative(numbers, n):

    present = set()
    for num in numbers:
        present.add(num)
    
    for i in range(1, n + 1):
        if i not in present:
            return i
    return None


if __name__ == "__main__":
    data = input("Введите числа через пробел: ")
    numbers = [int(x) for x in data.split()]
    n = max(numbers)
    
    print(f"Входные данные: {numbers}")
    print(f"Диапазон: 1..{n}")
    print(f"Недостающее число: {find_missing_imperative(numbers, n)}")


# функциональный

def find_missing_functional_sum(numbers, n):
    expected_sum = n * (n + 1) // 2
    actual_sum = sum(numbers)
    return expected_sum - actual_sum


if __name__ == "__main__":
    data = input("Введите числа через пробел: ")
    numbers = [int(x) for x in data.split()]
    n = max(numbers)
    
    print(f"Входные данные: {numbers}")
    print(f"Диапазон: 1..{n}")
    print(f"Недостающее число: {find_missing_functional_sum(numbers, n)}")