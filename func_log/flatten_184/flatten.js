// Упражнение 184. Выравнивание вложенного списка.
// функциональный

const flatten = (data) => {
    // Пустой список — пустой результат. data.slice и concat ниже его не меняют.
    if (data.length === 0) return [];
    const head = data[0];
    const tail = data.slice(1);
    // Голова-массив выравнивается целиком. Иначе это один элемент нового списка.
    const l1 = Array.isArray(head) ? flatten(head) : [head];
    // Хвост исходного списка, все элементы кроме первого.
    const l2 = flatten(tail);
    return l1.concat(l2);
};

const samples = [
    [1, [2, 3], [4, [5, [6, 7]]], [[[8], 9], [10]]],
    [],
    [1, 2, 3],
    [[[[1]]]],
    [[], [1, []], 2],
];

for (const data of samples) {
    console.log(JSON.stringify(flatten(data)));
}
// [1,2,3,4,5,6,7,8,9,10]
// []
// [1,2,3]
// [1]
// [1,2]
