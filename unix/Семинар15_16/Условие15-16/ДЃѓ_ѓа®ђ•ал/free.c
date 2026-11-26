//-----------------------------------------------------------------------------
//
// ОПИСАНИЕ
//
//       #include <sys/sysinfo.h>
//
//       int sysinfo(struct sysinfo *info);
//       
//       Начиная с Linux 2.3.16, sysinfo используется для получения информации в
//       следующей структуре:
//
//       struct sysinfo {
//                 long uptime;             /* секунд с момента начальной загрузки */
//                 unsigned long loads[3];  /* средняя загрузка системы за 1, 5 и 15 минут */
//                 unsigned long totalram;  /* общее количество оперативной памяти */
//                 unsigned long freeram;   /* объём доступной памяти */
//                 unsigned long sharedram; /* объём разделяемой памяти */
//                 unsigned long bufferram; /* память, используемая под буферы */
//                 unsigned long totalswap; /* общий объём своппинга */
//                 unsigned long freeswap;  /* доступно памяти на своппинге */
//                 unsigned short procs;    /* количество текущих процессов */
//                 char _f[22];             /* остаток структуры в 64 байта */
//       };
//
//------------------------------------------------------------------------------

/*
 * Краткий аналог команды free. Только Linux: sysinfo нет в macOS.
 * Заголовки linux/kernel.h и linux/sys.h для этого вызова не нужны,
 * достаточно sys/sysinfo.h.
 * Числа переводятся в килобайты делением на 1024.
 * В современном struct sysinfo размеры заданы в единицах mem_unit
 * (часто mem_unit == 1, то есть байты). Здесь mem_unit не учитывается.
 */

#include <stdio.h>
 
#include <linux/kernel.h>
#include <linux/sys.h>
#include <sys/sysinfo.h>
 
int main()
{
    struct sysinfo info;
    sysinfo(&info);
    int totalmem = info.totalram/1024;
    int usedmem = (info.totalram-info.freeram)/1024;
    int freemem = info.freeram/1024;
    int sharedmem = info.sharedram/1024;
    int bufferram = info.bufferram/1024;
    int totalswap = info.totalswap/1024;
    int usedswap = (info.totalswap-info.freeswap)/1024;
    int freeswap = info.freeswap/1024;
    int total = (info.totalram+info.totalswap)/1024;
    int used =((info.totalram-info.freeram)+(info.totalswap-info.freeswap))/1024;
    int free = (info.freeram+info.freeswap)/1024;
    printf("Total memory: %d\nUsed memory: %d\nFree memory: %d\nShared memory: %d\nBuffered: %d\n",
    totalmem, 
    usedmem,
    freemem,
    sharedmem, 
    bufferram);
    printf("Swap total: %d\nSwap used: %d\nSwap free: %d\n", 
    totalswap,
    usedswap,
    freeswap);
    printf("Total: %d\nTotal used: %d\nTotal free:%d\n",
    total,
    used,
    free);
}
