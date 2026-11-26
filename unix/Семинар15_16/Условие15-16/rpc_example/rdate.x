/*
 * Спецификация службы «удалённая дата» для rpcgen.
 *
 * Программа номер 1234567, версия 1, две процедуры:
 *   1. BIN_DATE — без аргументов, возвращает time() как long;
 *   2. STR_DATE — принимает этот long и возвращает строку ctime().
 *
 * rpcgen по этому файлу создаёт rdate.h, rdate_clnt.c, rdate_svc.c и rdate_xdr.c.
 */

program RDATE_PROG {
    version RDATE_VERS {
	long   BIN_DATE(void) = 1;
	string STR_DATE(long) = 2;
    } = 1;
} = 1234567;
