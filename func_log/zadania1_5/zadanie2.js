//нефункциональный 

function collatzImperative(n) {
    const sequence = [n];                       // изменяемое состояние
    while (n !== 1) {
        if (n % 2 === 0) {
            n = n / 2;                          // мутация переменной
        } else {
            n = n * 3 + 1;
        }
        sequence.push(n);                       // мутация массива
    }
    return sequence;
}

// Пример использования
const n = 5;
console.log(collatzImperative(n));              // [5, 16, 8, 4, 2, 1]

// функциональный
const collatzFunctional = n => {
    // чистая функция: результат зависит только от аргумента
    const step = x => (x % 2 === 0 ? x / 2 : x * 3 + 1);

    // рекурсия вместо цикла, иммутабельное расширение массива
    const go = (x, acc) => {
        if (x === 1) return acc;
        const nextX = step(x);
        return go(nextX, [...acc, nextX]);
    };

    return go(n, [n]);
};

// Пример использования
const n = 5;
console.log(collatzFunctional(n));              // [5, 16, 8, 4, 2, 1]
