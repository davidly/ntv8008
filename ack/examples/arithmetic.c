#include <stdio.h>
#include <stdint.h>

static unsigned checks;
static void check(int condition)
{
    if (!condition) { puts("FAIL"); }
    ++checks;
}
static int factorial(int n)
{
    return n > 1 ? n * factorial(n - 1) : 1;
}
static int mixed(int a, int b)
{
    int local = a * 3 + b;
    return local + factorial(6);
}
int main(void)
{
    unsigned a = 60000U, b = 251;
    int x = -12345, y = 321;
    unsigned char bytes[17];
    int words[7];
    unsigned i;
    volatile signed char negative = -1, minimum = -128;
    volatile unsigned char positive = 255;
    struct pair { unsigned char tag; int value; } p;
    check(sizeof(char) == 1 && sizeof(int) == 2 && sizeof(void *) == 2);
    check(a + 6000U == 464);
    check(a - 61000U == 64536U);
    check(a * 200 == 6912);
    check(a / b == 239 && a % b == 11);
    check(x / y == -38 && x % y == -147);
    check(x / -y == 38 && x % -y == -147);
    check(12345 / -y == -38 && 12345 % -y == 147);
    check((a & 255) == 96 && (a | 255) == 60159U);
    check((a ^ 255) == 60063U && (unsigned)~a == 5535);
    check((a >> 3) == 7500 && (b << 3) == 2008);
    check((x >> 3) == -1544);
    check((int)(signed char)255 == -1 && (unsigned char)-1 == 255);
    check(-32767 < 32767 && 32767 > -32767);
    check(60000U > 32767U && 32767U < 60000U);
    check(mixed(123, -9) == 1080);
    check((unsigned)negative == 65535U);
    check((unsigned)minimum == 65408U);
    check((int)positive == 255);
    check((signed char)positive == -1);
    for (i = 0; i < 17; ++i) bytes[i] = i * i;
    for (i = 0; i < 7; ++i) words[i] = -100 + i;
    check(bytes[16] == 0 && bytes[15] == 225 && words[6] == -94);
    p.tag = 7; p.value = -1234;
    check(p.tag == 7 && p.value == -1234);
    putu(checks); puts(" checks");
    return 0;
}
