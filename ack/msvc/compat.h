#ifndef ACK_MSVC_COMPAT_H
#define ACK_MSVC_COMPAT_H
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <io.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <ctype.h>
#define off_t _off_t
#define stat _stat
#define strdup _strdup
#define open _open
#define close _close
#define read _read
#define write _write
#define fileno _fileno
#define setmode _setmode
#define isatty _isatty
#define isascii __isascii
#define O_CREAT _O_CREAT
#define O_EXCL _O_EXCL
#define O_RDWR _O_RDWR
#define O_BINARY _O_BINARY
#ifndef CLOCK_REALTIME
#define CLOCK_REALTIME 0
#endif
#define clock_gettime(clock, ts) (timespec_get((ts), TIME_UTC) == TIME_UTC ? 0 : -1)
int ack_mkstemp(char*);
#define mkstemp ack_mkstemp
#endif
