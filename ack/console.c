/* Small freestanding console support; no hosted libc is linked. */
#include <stdio.h>
void putu(unsigned n)
{
    unsigned divisor = 10000;
    int started = 0;
    while (divisor) {
        unsigned digit = n / divisor;
        n %= divisor;
        if (digit || started || divisor == 1) {
            putchar('0' + digit);
            started = 1;
        }
        divisor /= 10;
    }
}
