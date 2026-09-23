// нефункциональный

function histogramImperative(numbers) {
    const lines = [];                 // изменяемое состояние
    for (let i = 0; i < numbers.length; i++) {   // явный счётчик
        let bar = "";
        for (let j = 0; j < numbers[i]; j++) {    // вложенный цикл
            bar += "#";               // мутация строки-аккумулятора
        }
        lines.push(bar);              // мутация массива
    }
    return lines;
}

const numbers = [10, 15, 7, 9, 1, 3];
histogramImperative(numbers).forEach(line => console.log(line));


// функциональный
const histogramFunctional = numbers =>
    numbers.map(n => "#".repeat(n));

const numbers = [10, 15, 7, 9, 1, 3];
console.log(histogramFunctional(numbers).join("\n"));