/*
 * Клиент READDIR.
 *
 * clnt_create находит сервер через portmapper (rpcbind) на указанной машине
 * и открывает TCP-соединение. Сам вызов делает readdir_1 из dir_clnt.c:
 * строка упаковывается в XDR, уходит на сервер, ответ распаковывается
 * в структуру readdir_res.
 *
 * Запуск: ./dir_client <хост> <каталог>
 * Каталог — путь на машине сервера, а не на машине клиента.
 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <rpc/rpc.h>

#include "dir.h"

int main(int argc, char *argv[])
{
	char *host;
	char *directory;
	CLIENT *client;
	readdir_res *result;
	namelist item;

	if (argc != 3) {
		fprintf(stderr, "Использование: %s <хост> <каталог>\n", argv[0]);
		return EXIT_FAILURE;
	}

	host = argv[1];
	directory = argv[2];

	/*
	 * xdr_string из спецификации ограничен MAXNAMELEN символами.
	 * Более длинное имя rpcgen отвергнет уже на клиенте, без понятного текста.
	 */
	if (strlen(directory) > MAXNAMELEN) {
		fprintf(stderr, "Имя каталога длиннее %d символов\n", MAXNAMELEN);
		return EXIT_FAILURE;
	}

	/* "tcp" — тот же транспорт, что регистрирует dir_server. */
	client = clnt_create(host, DIRPROG, DIRVERS, "tcp");
	if (client == NULL) {
		clnt_pcreateerror(host);
		return EXIT_FAILURE;
	}

	result = readdir_1(&directory, client);
	if (result == NULL) {
		/* Сеть или сервер ответили отказом: текст пишет clnt_perror. */
		clnt_perror(client, host);
		clnt_destroy(client);
		return EXIT_FAILURE;
	}

	if (result->err != 0) {
		/* Сервер дошёл до процедуры, но opendir/readdir не удались. */
		fprintf(stderr, "%s: %s\n", directory, strerror(result->err));
		clnt_destroy(client);
		return EXIT_FAILURE;
	}

	for (item = result->readdir_res_u.list; item != NULL; item = item->next)
		printf("%s\n", item->name);

	/*
	 * result указывает на static-буфер внутри readdir_1.
	 * Освобождать сам указатель нельзя. xdr_free освобождает только
	 * строки и узлы списка, которые клиентская заглушка выделила при разборе.
	 */
	xdr_free((xdrproc_t)xdr_readdir_res, (char *)result);
	clnt_destroy(client);
	return EXIT_SUCCESS;
}
