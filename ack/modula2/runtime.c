/* Original freestanding implementation of the supplied InOut definition. */
#include <stdio.h>
void _m2_init(void) {}
void _InOut__Write(int c) { putchar(c); }
void _InOut__WriteLn(void) { putchar('\n'); }
void _InOut__WriteString(char *s, unsigned low, unsigned high, unsigned stride)
{
    unsigned n = high-low+1;
    while (n-- && *s) { putchar(*s); s += stride; }
}
void _InOut__WriteCard(unsigned n, unsigned width)
{
    unsigned t=n, digits=1;
    while (t>=10) { ++digits; t/=10; }
    while (width>digits) { putchar(' '); --width; }
    putu(n);
}
void _InOut__WriteInt(int n, unsigned width)
{
    unsigned magnitude = n<0 ? 0U-(unsigned)n : (unsigned)n;
    unsigned t=magnitude, digits=1;
    while (t>=10) { ++digits; t/=10; }
    if (n<0) ++digits;
    while (width>digits) { putchar(' '); --width; }
    if (n<0) putchar('-');
    putu(magnitude);
}
void _InOut__Read(char *c) { *c=getchar(); }
/* ACK passes the divisor first for signed Modula-2 DIV/MOD. */
int dvi(int divisor, int dividend)
{
    int quotient=dividend/divisor;
    if (dividend%divisor && ((dividend<0)!=(divisor<0))) --quotient;
    return quotient;
}
int rmi(int divisor, int dividend)
{
    int remainder=dividend%divisor;
    if (remainder && ((dividend<0)!=(divisor<0))) remainder+=divisor;
    return remainder;
}
