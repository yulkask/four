# Упражнения 76 и 77. Методы join и replace заново, без str.join и str.replace.


def join(words, sep):
    """Склеивает список строк, вставляя sep между соседними элементами."""
    if not words:
        return ""
    head, *tail = words
    if not tail:
        return head
    return head + sep + join(tail, sep)


def replace_string(sentence, old_word, new_word):
    """Заменяет все вхождения old_word на new_word. Пустое old_word не ищет."""
    if old_word == "":
        return sentence

    def go(rest):
        if rest == "":
            return ""
        if rest.startswith(old_word):
            return new_word + go(rest[len(old_word):])
        return rest[0] + go(rest[1:])

    return go(sentence)


if __name__ == "__main__":
    # В тексте задания у первого ответа лишняя запятая, у второго — строчная
    # буква. join только вставляет разделитель и регистр не меняет.
    cases_join = [
        (["Привет", "Николай"], " ", "Привет Николай"),
        (["Привет", "Как дела?"], ", ", "Привет, Как дела?"),
    ]
    for words, sep, expected in cases_join:
        got = join(words, sep)
        print(f"join({words!r}, {sep!r}) = {got!r}")
        assert got == expected

    # Во втором тесте задания кавычки набраны с ошибкой: "Мне 50 лет" и "50".
    cases_replace = [
        ("Привет, Николай", "Николай", "Матильда", "Привет, Матильда"),
        ("Мне 50 лет", "50", "35", "Мне 35 лет"),
    ]
    for sentence, old, new, expected in cases_replace:
        got = replace_string(sentence, old, new)
        print(f"replace_string({sentence!r}, {old!r}, {new!r}) = {got!r}")
        assert got == expected

    print("Все тесты прошли.")
