/* Small C declarations and K&R definitions, including deep RAM-stack calls. */
#include <stdio.h>
int checks;
unsigned char bytes[260];
int words[3];
char signedbyte;

check(ok)
int ok;
{
    if (!ok) { puts("FAIL"); return 0; }
    ++checks;
    return 0;
}

deep(n)
int n;
{
    char odd;
    int local;
    odd = 7;
    local = n;
    if (n) return odd - 7 + local + deep(n - 1);
    return 0;
}

args(a, b, c)
int a, b, c;
{
    return a * 100 + b * 10 + c;
}

pick(n)
int n;
{
    switch (n) {
    case -300: return 3;
    case 0: return 5;
    case 257: return 7;
    default: return 11;
    }
}

main()
{
    unsigned int u, v;
    int i, j;
    int *p;
    char buffer[257];
    u = 65535; v = 256;
    check(u + 1 == 0);
    check(u > v);
    check(u / v == 255);
    check(u % v == 255);
    check(u * 3 == 65533);
    i = -1234; j = 37;
    check(i / j == -33);
    check(i % j == -13);
    check(-i / -j == -33);
    check(-i % -j == 13);
    check(i < j && i <= -1234 && j > i && j >= 37);
    check(!(0) && !!256 && !(-1 == 0));
    check((1 << 9) == 512 && (512 >> 8) == 2);
    check((i >> 1) == -617);
    check((u >> 8) == 255);
    check((u & 255) == 255 && (256 | 1) == 257);
    check((u ^ 255) == 65280 && ~u == 0);
    signedbyte = 255;
    check(signedbyte == -1);
    bytes[255] = 201; bytes[256] = 202;
    check(bytes[255] + bytes[256] == 403);
    words[0] = 123; words[1] = 456; words[2] = 789;
    p = words;
    check(*(p + 1) == 456 && *(1 + p) == 456);
    ++p;
    check(*p == 456 && p - words == 1);
    buffer[255] = 25; buffer[256] = 26;
    check(buffer[255] + buffer[256] == 51);
    check(args(1, 2, 3) == 123);
    check(deep(40) == 820);
    check(pick(-300) + pick(0) + pick(257) + pick(99) == 26);
    putu(checks); puts(" checks");
    return 0;
}
