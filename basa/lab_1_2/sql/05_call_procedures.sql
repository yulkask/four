-- =====================================================================
-- Продолжение. Проверка работоспособности хранимых процедур
-- (те же запросы, что в 02_regexp_queries.sql, но через CALL)
-- =====================================================================
SET NAMES utf8mb4;
USE library;

-- Авторы
CALL sp_search_authors('(^|, )Толст');          -- Толстой Л. Н., Толстой А. Н.
CALL sp_search_authors(',');                    -- книги нескольких авторов
CALL sp_search_authors('^[^,]+,[^,]+$');        -- ровно два автора

-- Название
CALL sp_search_title('[0-9]');                  -- в названии есть цифры
CALL sp_search_title('\\bи\\b');                -- «X и Y»
CALL sp_search_title('^[^ ]+ [^ ]+$');          -- ровно два слова

-- Издательство
CALL sp_search_publisher('^(АСТ|Эксмо)$');
CALL sp_search_publisher('^[a-z]');             -- зарубежные
CALL sp_search_publisher('литератур[а-я]*');

-- Год издания
CALL sp_search_year('^19[0-9]{2}$');            -- XX век
CALL sp_search_year('^201[5-9]$');              -- 2015–2019
CALL sp_search_year('[05]$');                   -- оканчивается на 0 или 5

-- Аннотация
CALL sp_search_annotation('программ[а-яё]*');
CALL sp_search_annotation('\\bлюб(овь|ви)\\b');
CALL sp_search_annotation('[0-9]{4}');

-- Универсальная процедура
CALL sp_search_books('authors', '^[A-Z][a-z]+ ', 1);   -- латиница, регистрозависимо
CALL sp_search_books('any', 'MySQL', 0);                -- во всех полях
CALL sp_search_books('title', 'война', 0);              -- без учёта регистра → «Война и мир»
CALL sp_search_books('title', 'война', 1);              -- с учётом регистра → пусто

-- Выходной параметр
CALL sp_count_matches('pub_year', '^20', @cnt);
SELECT @cnt AS books_21st_century;

-- Полнотекстовый поиск
CALL sp_fulltext_search('антиутопия', 'natural');
CALL sp_fulltext_search('+MySQL -репликация', 'boolean');
CALL sp_fulltext_search('алгоритм*', 'boolean');

-- Ошибка: неизвестное поле (ожидается SQLSTATE 45000)
-- CALL sp_search_books('isbn', '.*', 0);
