/* Classic BYTE odd-number sieve: 8191 candidates, ten iterations. */
#include <stdio.h>
static unsigned char flags[8191];
int main(void)
{
    unsigned i, k, prime, count = 0;
    int iteration;
    for (iteration = 0; iteration < 10; ++iteration) {
        for (i = 0; i < 8191; ++i) flags[i] = 1;
        count = 0;
        for (i = 0; i < 8191; ++i) {
            if (flags[i]) {
                prime = i + i + 3;
                for (k = i + prime; k < 8191; k += prime) flags[k] = 0;
                ++count;
            }
        }
    }
    putu(count); puts(" primes.");
    return 0;
}
