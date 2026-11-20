// Упражнения 76 и 77. Методы join и replace заново, без String.concat и Replace.

let rec join words sep =
    match words with
    | [] -> ""
    | [only] -> only
    | head :: tail -> head + sep + join tail sep

let replaceString sentence oldWord newWord =
    let rec go rest =
        if oldWord = "" || rest = "" then rest
        elif rest.StartsWith(oldWord) then
            newWord + go (rest.Substring(oldWord.Length))
        else
            string rest.[0] + go (rest.Substring(1))
    go sentence

let check name got expected =
    printfn "%s = %s" name got
    if got <> expected then
        failwithf "ожидалось %s" expected

// В тексте задания у первого ответа лишняя запятая, у второго — строчная буква.
check """join(["Привет"; "Николай"], " ")""" (join ["Привет"; "Николай"] " ") "Привет Николай"
check """join(["Привет"; "Как дела?"], ", ")""" (join ["Привет"; "Как дела?"] ", ") "Привет, Как дела?"

// Во втором тесте задания кавычки набраны с ошибкой: "Мне 50 лет" и "50".
check """replaceString("Привет, Николай", ...)""" (replaceString "Привет, Николай" "Николай" "Матильда") "Привет, Матильда"
check """replaceString("Мне 50 лет", ...)""" (replaceString "Мне 50 лет" "50" "35") "Мне 35 лет"

printfn "Все тесты прошли."
