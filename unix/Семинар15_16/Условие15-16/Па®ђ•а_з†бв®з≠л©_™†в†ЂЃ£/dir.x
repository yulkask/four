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