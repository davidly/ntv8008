/* Minimal unsigned decimal output, using only Small C's integer subset. */
putu(n)
unsigned int n;
{
    unsigned int place, digit;
    place = 10000;
    while (place > 1 && n / place == 0) place = place / 10;
    while (place) {
        digit = n / place;
        putchar('0' + digit);
        n = n % place;
        place = place / 10;
    }
    return 0;
}
