#!/bin/sh
# Собрать пример «удалённая дата».
# rpcgen читает rdate.x и создаёт заголовок и заглушки.
# Клиент линкуется со своей заглушкой rdate_clnt.c,
# сервер — с каркасом rdate_svc.c. Общий XDR-код rpcgen кладёт в rdate_xdr.c,
# но этот скрипт его к сборке не подключает: для таких простых типов
# часть старых rpcgen вкладывала XDR прямо в заглушки.

rpcgen rdate.x
gcc -o time_clnt time_clnt.c rdate_clnt.c
gcc -o time_svc time_svc.c rdate_svc.c
