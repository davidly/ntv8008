/* Original integer BASIC support for this freestanding 8008 target. */
#include <stdio.h>
void _hlt(int status);
void error(int number) { puts("ACK BASIC error"); _hlt(number); }
void _goto_err(void) { error(1); }
void _stop(void) { _hlt(0); }
void _setchan(int channel) { if (channel!=-1) error(2); }
void _nl(void) { putchar('\n'); }
void _qstmark(void) { putchar('?'); }
void _prinum(int n)
{
    unsigned magnitude=n<0 ? 0U-(unsigned)n : (unsigned)n;
    putchar(n<0 ? '-' : ' '); putu(magnitude); putchar(' ');
}
void _prstr(unsigned *s)
{
    unsigned length; char *p;
    if (!s) return;
    length=s[2]; p=(char *)s[0];
    while (length--) putchar(*p++);
}
void _zone(void) { putchar(' '); }
/* CHR$ uses static immutable one-character strings, so repeated loop output
   consumes no heap. Records are [address, reference count, length]. */
static char chars[128];
static unsigned strings[128][3];
unsigned *_chr(int n)
{
    unsigned c=(unsigned)n;
    if (c>127) { error(3); return 0; }
    chars[c]=c; strings[c][0]=(unsigned)&chars[c];
    strings[c][1]=9999; strings[c][2]=1;
    return strings[c];
}
static unsigned gosubs[64];
static unsigned depth;
void _gosub(unsigned label)
{
    if (depth==64) error(4);
    gosubs[depth++]=label;
}
unsigned _retstmt(void)
{
    if (!depth) { error(5); return 0; }
    return gosubs[--depth];
}
static int saved=-1;
static int basic_nextchar(void)
{
    int c;
    if (saved>=0) { c=saved; saved=-1; return c; }
    return getchar();
}
void _readint(int *value)
{
    int c,negative=0; unsigned n=0;
    do { c=basic_nextchar(); } while(c<=' ' || c==',');
    if (c=='-' || c=='+') { negative=c=='-'; c=basic_nextchar(); }
    if (c<'0' || c>'9') { error(6); return; }
    do { n=n*10+c-'0'; c=basic_nextchar(); } while(c>='0' && c<='9');
    saved=c; *value=negative ? (int)(0U-n) : (int)n;
}
int _length(unsigned *s) { return s ? s[2] : 0; }
int _asc(unsigned *s)
{
    if (!s || !s[2]) { error(7); return 0; }
    return *(unsigned char *)s[0];
}
int _strcomp(unsigned *right, unsigned *left)
{
    unsigned i=0, a, b, llen=left ? left[2] : 0, rlen=right ? right[2] : 0;
    while (i<llen && i<rlen) {
        a=((unsigned char *)left[0])[i]; b=((unsigned char *)right[0])[i];
        if (a!=b) return a>b ? 1 : -1;
        ++i;
    }
    return llen==rlen ? 0 : (llen>rlen ? 1 : -1);
}
void _intswap(int *a, int *b) { int t=*a; *a=*b; *b=t; }
