// нефункциональный

function maxIdenticalImperative(numbers) {
    if (numbers.length === 0) return null;
    
    let maxValue = numbers[0];
    let maxLength = 1;
    let currentValue = numbers[0];
    let currentLength = 1;
    
    for (let i = 1; i < numbers.length; i++) {
        if (numbers[i] === currentValue) {
            currentLength++;
        } else {
            if (currentLength > maxLength) {
                maxLength = currentLength;
                maxValue = currentValue;
            }
            currentValue = numbers[i];
            currentLength = 1;
        }
    }
    
    // Проверка последней последовательности
    if (currentLength > maxLength) {
        maxLength = currentLength;
        maxValue = currentValue;
    }
    
    return maxValue;
}

// Пример использования
const numbers = [2, 4, 6, 2, 2];
console.log("Результат:", maxIdenticalImperative(numbers));  // 2

// функциональный

const maxIdenticalFunctionalGroupBy = numbers => {
    if (numbers.length === 0) return null;
    
    // Группируем последовательные одинаковые элементы
    const groups = numbers.reduce((acc, num) => {
        if (acc.length === 0 || acc[acc.length - 1].value !== num) {
            acc.push({ value: num, length: 1 });
        } else {
            acc[acc.length - 1].length++;
        }
        return acc;
    }, []);
    
    // Находим группу с максимальной длиной (первая среди равных)
    const maxGroup = groups.reduce((max, group) =>
        group.length > max.length ? group : max
    );
    
    return maxGroup.value;
};

// Пример использования
const numbers = [2, 4, 6, 2, 2];
console.log("Результат:", maxIdenticalFunctionalGroupBy(numbers));  // 2