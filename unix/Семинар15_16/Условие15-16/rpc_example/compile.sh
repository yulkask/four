#!/bin/sh
rpcgen rdate.x
gcc -o time_clnt time_clnt.c rdate_clnt.c
gcc -o time_svc time_svc.c rdate_svc.c
