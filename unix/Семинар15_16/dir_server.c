/*
 * Серверная процедура READDIR.
 *
 * main() и разбор RPC-запроса находятся в dir_svc.c, который создаёт rpcgen.
 * Сюда rpcgen не пишет код: здесь только сама процедура readdir_1_svc.
 * Суффикс _1 — номер версии из dir.x, суффикс _svc — серверная сторона.
 *
 * Возвращать нужно указатель на память, которая переживёт возврат из функции:
 * каркас сервера сразу после возврата упакует результат в XDR и отправит его.
 * result объявлен static.
 */

#include <dirent.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <rpc/rpc.h>

#include "dir.h"

/* Освобождает список, собранный вручную, если вызов завершился ошибкой. */
static void free_list(namelist list)
{
	while (list != NULL) {
		namelist next = list->next;

		free(list->name);
		free(list);
		list = next;
	}
}

readdir_res *
readdir_1_svc(nametype *argp, struct svc_req *rqstp)
{
	static readdir_res result;

	DIR *dirp;
	struct dirent *entry;
	namelist *tail;

	(void)rqstp; /* сведения о запросе этой процедуре не нужны */

	/*
	 * Предыдущий успешный результат ещё лежит в result.
	 * xdr_free освобождает строки и узлы, которые rpcgen выделил при
	 * упаковке. При ошибке список мы освобождаем сами и оставляем его
	 * пустым, поэтому xdr_free вызывается только после успеха (err == 0).
	 */
	if (result.err == 0)
		xdr_free((xdrproc_t)xdr_readdir_res, (char *)&result);

	result.err = 0;
	result.readdir_res_u.list = NULL;

	/* argp — указатель на строку с именем каталога, присланную клиентом. */
	dirp = opendir(*argp);
	if (dirp == NULL) {
		result.err = errno;
		return &result;
	}

	/* tail указывает на то поле, куда нужно записать следующий узел. */
	tail = &result.readdir_res_u.list;
	errno = 0;
	while ((entry = readdir(dirp)) != NULL) {
		namelist node = malloc(sizeof(*node));

		if (node == NULL) {
			free_list(result.readdir_res_u.list);
			result.readdir_res_u.list = NULL;
			result.err = EAGAIN;
			closedir(dirp);
			return &result;
		}

		node->name = strdup(entry->d_name);
		node->next = NULL;
		if (node->name == NULL) {
			free(node);
			free_list(result.readdir_res_u.list);
			result.readdir_res_u.list = NULL;
			result.err = EAGAIN;
			closedir(dirp);
			return &result;
		}

		*tail = node;
		tail = &node->next;
	}

	if (errno != 0) {
		int saved = errno;

		free_list(result.readdir_res_u.list);
		result.readdir_res_u.list = NULL;
		result.err = saved;
		closedir(dirp);
		return &result;
	}

	closedir(dirp);
	result.err = 0;
	return &result;
}
