-- =====================================================================
-- Пункт 5. Полнотекстовый поиск по полю «аннотация»
-- (индекс ft_annotation создаётся в 01_schema.sql)
--
-- InnoDB: минимальная длина слова в индексе — 3 символа
-- (innodb_ft_min_token_size), короткие слова («и», «о») не индексируются.
-- =====================================================================
SET NAMES utf8mb4;
USE library;

-- 5.1. Естественный язык (NATURAL LANGUAGE MODE) с оценкой релевантности
SELECT id, title,
       MATCH(annotation) AGAINST ('антиутопия' IN NATURAL LANGUAGE MODE) AS score
FROM books
WHERE MATCH(annotation) AGAINST ('антиутопия' IN NATURAL LANGUAGE MODE)
ORDER BY score DESC;

-- 5.2. Несколько слов: найдутся книги, где есть хотя бы одно из них
SELECT id, title,
       MATCH(annotation) AGAINST ('роман любви' IN NATURAL LANGUAGE MODE) AS score
FROM books
WHERE MATCH(annotation) AGAINST ('роман любви' IN NATURAL LANGUAGE MODE)
ORDER BY score DESC;

-- 5.3. Логический режим: обязательно «MySQL», обязательно «репликация»
SELECT id, title FROM books
WHERE MATCH(annotation) AGAINST ('+MySQL +репликация' IN BOOLEAN MODE);

-- 5.4. Логический режим: «MySQL», но без «репликация»
SELECT id, title FROM books
WHERE MATCH(annotation) AGAINST ('+MySQL -репликация' IN BOOLEAN MODE);

-- 5.5. Усечение: все слова, начинающиеся на «алгоритм» (алгоритмам, алгоритмы…)
SELECT id, title FROM books
WHERE MATCH(annotation) AGAINST ('алгоритм*' IN BOOLEAN MODE);

-- 5.6. Точная фраза
SELECT id, title FROM books
WHERE MATCH(annotation) AGAINST ('"хранимые процедуры"' IN BOOLEAN MODE);

-- 5.7. Одно из слов, с повышением веса для «роман» и понижением для «повесть»
SELECT id, title,
       MATCH(annotation) AGAINST ('>роман <повесть' IN BOOLEAN MODE) AS score
FROM books
WHERE MATCH(annotation) AGAINST ('>роман <повесть' IN BOOLEAN MODE)
ORDER BY score DESC;

-- 5.8. Поиск по английской аннотации
SELECT id, title FROM books
WHERE MATCH(annotation) AGAINST ('+JavaScript +asynchronous' IN BOOLEAN MODE);

-- 5.9. Расширение запроса (второй проход по словам из найденных документов)
SELECT id, title FROM books
WHERE MATCH(annotation) AGAINST ('антиутопия' WITH QUERY EXPANSION);
