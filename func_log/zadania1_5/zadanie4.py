# ============================================
# Задача 4: Найти недостающее число
# ============================================

# Нефункциональный (императивный) подход
def find_missing_imperative(numbers, n):
    """
    Нефункциональный подход: использует мутируемое множество 
    и явные циклы для поиска недостающего числа.
    
    Почему это НЕ функционально:
    - Мутация множества: add() изменяет present на месте
    - Явные циклы: два цикла for управляют ходом пошагово
    - Изменяемое состояние: логика зависит от текущего содержимого present
    - Ранний выход: return внутри цикла зависит от порядка вычисления
    """
    present = set()
    for num in numbers:
        present.add(num)
    
    for i in range(1, n + 1):
        if i not in present:
            return i
    return None


# Функциональный подход (математический - через сумму)
def find_missing_functional_sum(numbers, n):
    """
    Функциональный подход: использует математическую формулу.
    Сумма 1..n минус сумма данных чисел = недостающее число.
    
    Почему это функционально:
    - Чистые функции: результат зависит только от аргументов
    - Нет мутаций: просто вычисление по формуле
    - Нет циклов: используются встроенные функции высокого уровня
    - Декларативность: выражает идею "разница между ожидаемой и реальной суммой"
    - Иммутабельность: никакие данные не изменяются
    """
    expected_sum = n * (n + 1) // 2
    actual_sum = sum(numbers)
    return expected_sum - actual_sum


# Функциональный подход (через XOR и reduce)
def find_missing_functional_xor(numbers, n):
    """
    Функциональный подход: использует XOR.
    XOR одинаковых чисел даёт 0, поэтому остаётся только недостающее.
    
    Почему это функционально:
    - Использует reduce - классический функциональный паттерн свёртки (fold)
    - Чистые функции: лямбда без побочных эффектов
    - Композиция: несколько reduce вызовов скомпонованы вместе
    - Нет изменяемого состояния: каждый reduce возвращает новый аккумулятор
    - Декларативность: описывает операцию логически, а не пошагово
    """
    from functools import reduce
    
    all_xor = reduce(lambda acc, x: acc ^ x, range(1, n + 1), 0)
    data_xor = reduce(lambda acc, x: acc ^ x, numbers, 0)
    return all_xor ^ data_xor


if __name__ == "__main__":
    print("=" * 70)
    print("ЗАДАЧА 4: НАЙТИ НЕДОСТАЮЩЕЕ ЧИСЛО")
    print("=" * 70)
    print()
    
    # Ввод данных от пользователя
    data = input("Введите числа через пробел: ")
    numbers = list(map(int, data.split()))
    n = max(numbers)
    
    print()
    print("Входные данные:", numbers)
    print("Диапазон: 1 до", n)
    print()
    
    print("-" * 70)
    print("НЕФУНКЦИОНАЛЬНЫЙ ПОДХОД (императивный)")
    print("-" * 70)
    result_imperative = find_missing_imperative(numbers, n)
    print(f"Недостающее число: {result_imperative}")
    print()
    
    print("-" * 70)
    print("ФУНКЦИОНАЛЬНЫЙ ПОДХОД (через сумму)")
    print("-" * 70)
    result_functional_sum = find_missing_functional_sum(numbers, n)
    print(f"Недостающее число: {result_functional_sum}")
    print()
    
    print("-" * 70)
    print("ФУНКЦИОНАЛЬНЫЙ ПОДХОД (через XOR и reduce)")
    print("-" * 70)
    result_functional_xor = find_missing_functional_xor(numbers, n)
    print(f"Недостающее число: {result_functional_xor}")
    print()
