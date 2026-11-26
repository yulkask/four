# rpcgen по dir.x создаёт заголовок, заглушки и каркас сервера.
# -C — прототипы ANSI C, их ожидают dir_client.c и dir_server.c.
# RPC_SVC_FG не даёт сгенерированному main уйти в фон: сервер остаётся
# в терминале, пока его не остановят Ctrl+C.

CC = gcc
# Заглушки rpcgen приводят xdr_* к xdrproc_t и используют старые прототипы.
# Новый clang считает это ошибкой, хотя так устроен сам rpcgen. Флаги ниже
# глушат только эти предупреждения сгенерированного кода.
CFLAGS = -Wall -Wextra -DRPC_SVC_FG \
	-Wno-incompatible-function-pointer-types \
	-Wno-cast-function-type-mismatch \
	-Wno-deprecated-non-prototype \
	-Wno-pointer-sign \
	-Wno-unused-parameter

.PHONY: all clean

all: dir_client dir_server

dir.h dir_clnt.c dir_svc.c dir_xdr.c: dir.x
	rpcgen -C dir.x

dir_client: dir_client.c dir_clnt.c dir_xdr.c dir.h
	$(CC) $(CFLAGS) -o $@ dir_client.c dir_clnt.c dir_xdr.c

dir_server: dir_server.c dir_svc.c dir_xdr.c dir.h
	$(CC) $(CFLAGS) -o $@ dir_server.c dir_svc.c dir_xdr.c

clean:
	rm -f dir.h dir_clnt.c dir_svc.c dir_xdr.c dir_client dir_server
