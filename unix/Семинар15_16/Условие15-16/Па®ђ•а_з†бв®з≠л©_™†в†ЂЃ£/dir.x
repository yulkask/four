/*
 * Частичный пример из методички: только спецификация READDIR.
 * Клиента в этом каталоге нет, серверная процедура — в dir_server.c.
 * Готовая программа собрана уровнем выше, в Семинар15_16.
 *
 * Клиент передаёт имя каталога. При err = 0 сервер возвращает список имён,
 * иначе err — это errno, а список по сети не передаётся.
 */

const MAXNAMELEN = 255;

typedef string nametype<MAXNAMELEN>;
typedef struct namenode *namelist;

struct namenode {
    nametype name;
    namelist next;
};

union readdir_res switch (int err) {
    case 0:
            namelist list;
    default:
            void;
};

program DIRPROG {
    version DIRVERS {
    readdir_res
    READDIR(nametype) = 1;
    } = 1;
} = 0x20000076;
