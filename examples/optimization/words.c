#include <stdio.h>
/* Values are 0..127. Only the element type differs between versions. */
int values[128];
main()
{
    int i, pass, sum;
    for (i = 0; i < 128; i++) values[i] = i;
    for (pass = 0; pass < 10; pass++) {
        sum = 0;
        for (i = 0; i < 128; i++) sum += values[i];
    }
    putu(sum);
    putchar('\n');
    return 0;
}
