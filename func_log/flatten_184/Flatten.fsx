// Упражнение 184. Выравнивание вложенного списка.
// функциональный
// У F# список однороден, поэтому вложенность задаётся своим типом:
// Atom — число, Nested — список таких же значений.

type Nested =
    | Atom of int
    | Nested of Nested list

let rec flatten data =
    match data with
    | [] -> []
    | head :: tail ->
        let l1 =
            match head with
            | Nested inner -> flatten inner
            | Atom n -> [n]
        // Хвост data: все элементы, кроме первого.
        let l2 = flatten tail
        l1 @ l2

let show items =
    "[" + (items |> List.map string |> String.concat "; ") + "]"

let samples = [
    [ Atom 1
      Nested [ Atom 2; Atom 3 ]
      Nested [ Atom 4; Nested [ Atom 5; Nested [ Atom 6; Atom 7 ] ] ]
      Nested [ Nested [ Nested [ Atom 8 ]; Atom 9 ]; Nested [ Atom 10 ] ] ]
    []
    [ Atom 1; Atom 2; Atom 3 ]
    [ Nested [ Nested [ Nested [ Atom 1 ] ] ] ]
    [ Nested []; Nested [ Atom 1; Nested [] ]; Atom 2 ]
]

samples
|> List.iter (fun data -> printfn "%s" (show (flatten data)))
// [1; 2; 3; 4; 5; 6; 7; 8; 9; 10]
// []
// [1; 2; 3]
// [1]
// [1; 2]
