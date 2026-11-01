#include <stdio.h>

main()
{
    int i, pass, sum;
    for (pass = 0; pass < 10; pass++) {
        sum = 0;
        for (i = 0; i < 128; i++) sum += i+i;
    }
    putu(sum);
    putchar('\n');
    return 0;
}
