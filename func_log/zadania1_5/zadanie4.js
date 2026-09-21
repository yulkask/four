// нефункциональный

function findMissingImperative(numbers, n) {
    const present = new Set();
    for (let num of numbers) {
        present.add(num);
    }
    
    for (let i = 1; i <= n; i++) {
        if (!present.has(i)) {
            return i;
        }
    }
    return null;
}

// Пример использования
const numbers = [1, 2, 3, 5, 6];
const n = Math.max(...numbers);
console.log("Результат:", findMissingImperative(numbers, n));  // 4


// функциональный

const findMissingFunctionalSum = (numbers, n) => {
    const expectedSum = (n * (n + 1)) / 2;
    const actualSum = numbers.reduce((acc, x) => acc + x, 0);
    return expectedSum - actualSum;
};

// Пример использования
const numbers = [1, 2, 3, 5, 6];
const n = Math.max(...numbers);
console.log("Результат:", findMissingFunctionalSum(numbers, n));  // 4