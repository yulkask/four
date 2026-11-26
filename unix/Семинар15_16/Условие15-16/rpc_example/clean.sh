#!/bin/sh
# Удалить всё, что создали rpcgen и gcc. Исходники time_*.c и rdate.x остаются.

rm rdate.h
rm rdate_clnt.c
rm rdate_svc.c
rm time_clnt
rm time_svc
