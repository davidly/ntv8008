#include "compat.h"
#include <errno.h>
int ack_mkstemp(char* name)
{
    if (_mktemp_s(name, strlen(name)+1)) return -1;
    return _open(name, _O_RDWR | _O_CREAT | _O_EXCL | _O_BINARY, _S_IREAD | _S_IWRITE);
}
