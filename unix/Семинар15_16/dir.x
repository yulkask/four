/*
 * Описание удалённой процедуры для rpcgen.
 *
 * Клиент передаёт имя каталога на сервере (строка не длиннее MAXNAMELEN).
 * Сервер возвращает либо список имён (err = 0), либо код ошибки errno
 * (err != 0), и тогда список по сети не передаётся.
 *
 * Номер программы 0x20000076 лежит в пользовательском диапазоне
 * 0x20000000–0x3fffffff: его можно регистрировать в portmapper,
 * не пересекаясь со стандартными службами Sun RPC.
 */

const MAXNAMELEN = 255;

/* Строка ограниченной длины. rpcgen превратит её в char *. */
typedef string nametype<MAXNAMELEN>;

/* Односвязный список имён. Указатель, потому что список рекурсивный. */
typedef struct namenode *namelist;

struct namenode {
	nametype name;   /* имя одного элемента каталога */
	namelist next;   /* следующий элемент или NULL в конце списка */
};

/*
 * Размеченное объединение. Поле err — дискриминант:
 *   0       — в объединении лежит list;
 *   иначе   — объединение пустое, err равен errno с сервера.
 */
union readdir_res switch (int err) {
	case 0:
		namelist list;
	default:
		void;
};

program DIRPROG {
	version DIRVERS {
		readdir_res
		READDIR(nametype) = 1;   /* процедура номер 1 */
	} = 1;                           /* версия 1 */
} = 0x20000076;
