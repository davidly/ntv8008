/* Freestanding Pascal support written for this 8008 target. No libpc linked. */
#include <stdio.h>
void _hlt(int status);
void _ini(unsigned args, int count, unsigned files, unsigned mainframe) {}

static void fail(char *message)
{
    puts(message);
    _hlt(1);
}

void _wrc(int c, unsigned file) { putchar(c); }
void _wln(unsigned file) { putchar('\n'); }
void _wrs(int length, char *s, unsigned file)
{
    while (length-- > 0) putchar(*s++);
}
void _wss(int width, int length, char *s, unsigned file)
{
    if (width < 0 || length < 0) fail("Pascal invalid output width");
    if (length > width) length = width;
    while (width-- > length) putchar(' ');
    _wrs(length, s, file);
}
void _wsc(int width, int c, unsigned file)
{
    if (width < 0) fail("Pascal invalid output width");
    while (width-- > 1) putchar(' ');
    putchar(c);
}
void _wsi(int width, int n, unsigned file)
{
    unsigned magnitude, t;
    int digits = 1;
    if (width < 0) fail("Pascal invalid output width");
    magnitude = n < 0 ? 0U - (unsigned)n : (unsigned)n;
    t = magnitude;
    while (t >= 10) { ++digits; t /= 10; }
    if (n < 0) ++digits;
    while (width-- > digits) putchar(' ');
    if (n < 0) putchar('-');
    putu(magnitude);
}
void _wri(int n, unsigned file) { _wsi(6,n,file); }
void _wsb(int width, int b, unsigned file)
{
    if (b) _wss(width,4,"true",file);
    else _wss(width,5,"false",file);
}
void _wrb(int b, unsigned file) { _wsb(5,b,file); }
int _dvi(int divisor, int dividend) { return dividend / divisor; }
int _mdi(int divisor, int dividend)
{
    int r;
    if (divisor <= 0) fail("Pascal invalid MOD divisor");
    r = dividend % divisor;
    return r < 0 ? r+divisor : r;
}
int _abi(int n) { return n < 0 ? -n : n; }
int _sqi(int n) { return n*n; }
unsigned _pc_aar(unsigned *descriptor, int index, unsigned base)
{
    return base + (index-descriptor[0])*descriptor[2];
}
unsigned _pc_lar(unsigned *descriptor, int index, unsigned base)
{
    unsigned address = _pc_aar(descriptor,index,base);
    if (descriptor[2] == 1) return *(unsigned char *)address;
    if (descriptor[2] == 2) return *(unsigned *)address;
    fail("Pascal unsupported array element size");
    return 0;
}
void _pc_sar(unsigned *descriptor, int index, unsigned base, unsigned value)
{
    unsigned address = _pc_aar(descriptor,index,base);
    if (descriptor[2] == 1) *(unsigned char *)address = value;
    else if (descriptor[2] == 2) *(unsigned *)address = value;
    else fail("Pascal unsupported array element size");
}

static int saved = -1;
static int nextchar(void)
{
    int c;
    if (saved >= 0) { c=saved; saved=-1; return c; }
    return getchar();
}
int _rdc(unsigned file) { return nextchar(); }
void _rln(unsigned file) { while (nextchar() != '\n') {} }
int _rdi(unsigned file)
{
    int c, sign=0;
    unsigned n=0;
    do { c=nextchar(); } while (c <= ' ');
    if (c=='-' || c=='+') { sign=(c=='-'); c=nextchar(); }
    if (c<'0' || c>'9') fail("Pascal invalid integer input");
    do { n=n*10+c-'0'; c=nextchar(); } while(c>='0' && c<='9');
    saved=c;
    return sign ? (int)(0U-n) : (int)n;
}
