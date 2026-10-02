-- =====================================================================
-- Продолжение. Хранимые процедуры для запросов из пункта 2
-- (выполнять во вкладке «SQL» phpMyAdmin; разделитель $$ указан ниже,
--  либо в поле «Разделитель» под окном запроса)
-- =====================================================================
SET NAMES utf8mb4;
USE library;

DROP PROCEDURE IF EXISTS sp_search_authors;
DROP PROCEDURE IF EXISTS sp_search_title;
DROP PROCEDURE IF EXISTS sp_search_publisher;
DROP PROCEDURE IF EXISTS sp_search_year;
DROP PROCEDURE IF EXISTS sp_search_annotation;
DROP PROCEDURE IF EXISTS sp_search_books;
DROP PROCEDURE IF EXISTS sp_count_matches;
DROP PROCEDURE IF EXISTS sp_fulltext_search;

DELIMITER $$

-- Поиск по полю «Авторы» по регулярному выражению
CREATE PROCEDURE sp_search_authors(IN p_pattern VARCHAR(255))
    COMMENT 'Поиск книг по авторам (REGEXP)'
BEGIN
    SELECT id, authors, title, publisher, pub_year
    FROM books
    WHERE authors REGEXP p_pattern
    ORDER BY authors;
END$$

-- Поиск по полю «Название»
CREATE PROCEDURE sp_search_title(IN p_pattern VARCHAR(255))
    COMMENT 'Поиск книг по названию (REGEXP)'
BEGIN
    SELECT id, authors, title, publisher, pub_year
    FROM books
    WHERE title REGEXP p_pattern
    ORDER BY title;
END$$

-- Поиск по полю «Издательство»
CREATE PROCEDURE sp_search_publisher(IN p_pattern VARCHAR(255))
    COMMENT 'Поиск книг по издательству (REGEXP)'
BEGIN
    SELECT id, authors, title, publisher, pub_year
    FROM books
    WHERE publisher REGEXP p_pattern
    ORDER BY publisher, title;
END$$

-- Поиск по полю «Год издания»
CREATE PROCEDURE sp_search_year(IN p_pattern VARCHAR(255))
    COMMENT 'Поиск книг по году издания (REGEXP)'
BEGIN
    SELECT id, authors, title, publisher, pub_year
    FROM books
    WHERE pub_year REGEXP p_pattern
    ORDER BY pub_year;
END$$

-- Поиск по полю «Аннотация»; дополнительно возвращает первый найденный фрагмент
CREATE PROCEDURE sp_search_annotation(IN p_pattern VARCHAR(255))
    COMMENT 'Поиск книг по аннотации (REGEXP)'
BEGIN
    SELECT id, authors, title, publisher, pub_year,
           REGEXP_SUBSTR(annotation, p_pattern) AS fragment,
           annotation
    FROM books
    WHERE annotation REGEXP p_pattern
    ORDER BY id;
END$$

-- Универсальная процедура: поле задаётся параметром,
-- p_case_sensitive = 1 включает регистрозависимый поиск
CREATE PROCEDURE sp_search_books(
    IN p_field          VARCHAR(20),
    IN p_pattern        VARCHAR(255),
    IN p_case_sensitive TINYINT
)
    COMMENT 'Поиск книг по регулярному выражению в выбранном поле'
BEGIN
    DECLARE v_flags CHAR(1) DEFAULT IF(p_case_sensitive = 1, 'c', 'i');

    IF p_field NOT IN ('authors', 'title', 'publisher', 'pub_year', 'annotation', 'any') THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Неизвестное поле: допустимы authors, title, publisher, pub_year, annotation, any';
    END IF;

    SELECT id, authors, title, publisher, pub_year, annotation
    FROM books
    WHERE CASE p_field
              WHEN 'authors'    THEN REGEXP_LIKE(authors,    p_pattern, v_flags)
              WHEN 'title'      THEN REGEXP_LIKE(title,      p_pattern, v_flags)
              WHEN 'publisher'  THEN REGEXP_LIKE(publisher,  p_pattern, v_flags)
              WHEN 'pub_year'   THEN REGEXP_LIKE(pub_year,   p_pattern, v_flags)
              WHEN 'annotation' THEN REGEXP_LIKE(annotation, p_pattern, v_flags)
              WHEN 'any'        THEN REGEXP_LIKE(authors,    p_pattern, v_flags)
                                  OR REGEXP_LIKE(title,      p_pattern, v_flags)
                                  OR REGEXP_LIKE(publisher,  p_pattern, v_flags)
                                  OR REGEXP_LIKE(pub_year,   p_pattern, v_flags)
                                  OR REGEXP_LIKE(annotation, p_pattern, v_flags)
          END
    ORDER BY id;
END$$

-- Количество совпадений по полю в выходном параметре
CREATE PROCEDURE sp_count_matches(
    IN  p_field   VARCHAR(20),
    IN  p_pattern VARCHAR(255),
    OUT p_count   INT
)
    COMMENT 'Число книг, у которых поле соответствует регулярному выражению'
BEGIN
    SELECT COUNT(*) INTO p_count
    FROM books
    WHERE CASE p_field
              WHEN 'authors'    THEN authors    REGEXP p_pattern
              WHEN 'title'      THEN title      REGEXP p_pattern
              WHEN 'publisher'  THEN publisher  REGEXP p_pattern
              WHEN 'pub_year'   THEN pub_year   REGEXP p_pattern
              WHEN 'annotation' THEN annotation REGEXP p_pattern
              ELSE FALSE
          END;
END$$

-- Полнотекстовый поиск по аннотации: p_mode = 'natural' | 'boolean' | 'expansion'
CREATE PROCEDURE sp_fulltext_search(IN p_query VARCHAR(255), IN p_mode VARCHAR(10))
    COMMENT 'Полнотекстовый поиск по аннотации'
BEGIN
    IF p_mode = 'boolean' THEN
        SELECT id, authors, title, publisher, pub_year, annotation,
               MATCH(annotation) AGAINST (p_query IN BOOLEAN MODE) AS score
        FROM books
        WHERE MATCH(annotation) AGAINST (p_query IN BOOLEAN MODE)
        ORDER BY score DESC;
    ELSEIF p_mode = 'expansion' THEN
        SELECT id, authors, title, publisher, pub_year, annotation,
               MATCH(annotation) AGAINST (p_query WITH QUERY EXPANSION) AS score
        FROM books
        WHERE MATCH(annotation) AGAINST (p_query WITH QUERY EXPANSION)
        ORDER BY score DESC;
    ELSE
        SELECT id, authors, title, publisher, pub_year, annotation,
               MATCH(annotation) AGAINST (p_query IN NATURAL LANGUAGE MODE) AS score
        FROM books
        WHERE MATCH(annotation) AGAINST (p_query IN NATURAL LANGUAGE MODE)
        ORDER BY score DESC;
    END IF;
END$$

DELIMITER ;

SHOW PROCEDURE STATUS WHERE Db = 'library';
