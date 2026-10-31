/* Decimal spigot: DIGITS=200 produces 192 digits of e. */
#include <stdio.h>
#define DIGITS 200
static unsigned char a[DIGITS];
int main(void)
{
    unsigned high = DIGITS, n, x = 0;
    for (n = 2; n < DIGITS; ++n) a[n] = 1;
    a[0] = 0; a[1] = 2;
    while (high > 9) {
        --high;
        for (n = high; n; --n) {
            a[n] = x % n;
            x = 10 * a[n - 1] + x / n;
        }
        if (x >= 10) putchar('0' + x / 10);
        putchar('0' + x % 10);
    }
    putchar('\n'); puts("done.");
    return 0;
}
