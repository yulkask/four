// нефункциональный

function reverseStringImperative(s) {
    let result = "";
    for (let i = s.length - 1; i >= 0; i--) {
        result += s[i];
    }
    return result;
}

console.log(reverseStringImperative("Hello"));  // olleH


// функциональный

const reverseStringFunctional = s => 
    s.split('').reverse().join('');

console.log(reverseStringFunctional("Hello"));  // olleH
