#ifndef ACK8008_STDDEF_H
#define ACK8008_STDDEF_H
#define NULL ((void *)0)
typedef unsigned size_t;
typedef int ptrdiff_t;
#define offsetof(type, member) ((size_t)&(((type *)0)->member))
#endif
