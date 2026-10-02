-- =====================================================================
-- Пункт 2. Поисковые запросы к каждому полю с регулярными выражениями
-- Пункт 3. Выполнять во вкладке «SQL» phpMyAdmin (база library)
--
-- В MySQL 8 REGEXP использует библиотеку ICU (поддерживает Unicode,
-- \b, {n,m}, классы и т. д.). Обратный слеш в строке SQL удваивается: '\\b'.
-- При collation *_ci REGEXP нечувствителен к регистру; для
-- регистрозависимого поиска — REGEXP_LIKE(поле, шаблон, 'c').
-- =====================================================================
SET NAMES utf8mb4;
USE library;

-- ---------------------------------------------------------------------
-- 2.1. Поле «Авторы» (authors)
-- ---------------------------------------------------------------------

-- а) Авторы, фамилия которых начинается на «Толст» (Толстой Л. Н., Толстой А. Н.)
SELECT id, authors, title FROM books
WHERE authors REGEXP '(^|, )Толст';

-- б) Книги с несколькими авторами (в поле есть запятая)
SELECT id, authors, title FROM books
WHERE authors REGEXP ',';

-- в) Книги ровно двух авторов: «Фамилия И. О., Фамилия И. О.»
SELECT id, authors, title FROM books
WHERE authors REGEXP '^[^,]+,[^,]+$';

-- г) Авторы с латинскими именами (регистрозависимо)
SELECT id, authors, title FROM books
WHERE REGEXP_LIKE(authors, '^[A-Z][a-z]+ ', 'c');

-- д) Автор записан с двумя инициалами «И. О.»
SELECT id, authors FROM books
WHERE REGEXP_LIKE(authors, '^[А-ЯЁ][а-яё]+ [А-ЯЁ]\\. [А-ЯЁ]\\.$', 'c');

-- ---------------------------------------------------------------------
-- 2.2. Поле «Название» (title)
-- ---------------------------------------------------------------------

-- а) Названия, содержащие цифры («1984», «451 градус…», «Том 1»)
SELECT id, title FROM books
WHERE title REGEXP '[0-9]';

-- б) Названия вида «X и Y» (союз «и» отдельным словом)
SELECT id, title FROM books
WHERE title REGEXP '\\bи\\b';

-- в) Названия ровно из двух слов
SELECT id, title FROM books
WHERE title REGEXP '^[^ ]+ [^ ]+$';

-- г) Названия с подзаголовком (после точки, двоеточия или запятой)
SELECT id, title FROM books
WHERE title REGEXP '[.:,] ';

-- д) Названия, начинающиеся с «Мастер» или «Война»
SELECT id, title FROM books
WHERE title REGEXP '^(Мастер|Война)';

-- ---------------------------------------------------------------------
-- 2.3. Поле «Издательство» (publisher)
-- ---------------------------------------------------------------------

-- а) Издательство АСТ или Эксмо (точное совпадение)
SELECT id, title, publisher FROM books
WHERE publisher REGEXP '^(АСТ|Эксмо)$';

-- б) Зарубежные издательства (латиница)
SELECT id, title, publisher FROM books
WHERE publisher REGEXP '^[a-z]';

-- в) Название издательства из нескольких слов или через дефис
SELECT id, title, publisher FROM books
WHERE publisher REGEXP '[ -]';

-- г) Издательства, в названии которых есть «литература»
SELECT id, title, publisher FROM books
WHERE publisher REGEXP 'литератур[а-я]*';

-- ---------------------------------------------------------------------
-- 2.4. Поле «Год издания» (pub_year)
-- ---------------------------------------------------------------------

-- а) Книги, изданные в XX веке (1901–2000 ≈ 19xx)
SELECT id, title, pub_year FROM books
WHERE pub_year REGEXP '^19[0-9]{2}$';

-- б) Книги, изданные в 2015–2019 годах
SELECT id, title, pub_year FROM books
WHERE pub_year REGEXP '^201[5-9]$';

-- в) Книги 2020-х годов
SELECT id, title, pub_year FROM books
WHERE pub_year REGEXP '^202[0-9]$';

-- г) «Юбилейные» годы — оканчиваются на 0 или 5
SELECT id, title, pub_year FROM books
WHERE pub_year REGEXP '[05]$';

-- ---------------------------------------------------------------------
-- 2.5. Поле «Аннотация» (annotation)
-- ---------------------------------------------------------------------

-- а) Любые формы слов «программа / программирование / программный»
SELECT id, title FROM books
WHERE annotation REGEXP 'программ[а-яё]*';

-- б) В аннотации упоминаются годы (четыре цифры подряд)
SELECT id, title, REGEXP_SUBSTR(annotation, '[0-9]{4}') AS first_year
FROM books
WHERE annotation REGEXP '[0-9]{4}';

-- в) Слово «любовь» в любом падеже (любовь, любви)
SELECT id, title FROM books
WHERE annotation REGEXP '\\bлюб(овь|ви)\\b';

-- г) Жанр — роман или повесть в любой форме
SELECT id, title,
       REGEXP_SUBSTR(annotation, '\\b(роман|повест)[а-яё]*') AS genre_word
FROM books
WHERE annotation REGEXP '\\b(роман|повест)[а-яё]*';

-- д) Аннотации на английском языке (нет ни одной кириллической буквы)
SELECT id, title FROM books
WHERE annotation NOT REGEXP '[а-яё]';

-- е) Аннотации, где есть слово «MySQL» или «SQL»
SELECT id, title FROM books
WHERE annotation REGEXP '\\b(My)?SQL\\b';
