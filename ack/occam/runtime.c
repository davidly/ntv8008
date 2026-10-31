/* Original sequential console-channel runtime. No upstream Occam library. */
#include <stdio.h>
unsigned file[40];
unsigned worddes[3], bytedes[3], chandes[3];
int any;
void _hlt(int status);
static void occam_fail(char *message) { puts(message); _hlt(1); }
void init(void)
{
    worddes[0]=bytedes[0]=chandes[0]=0;
    worddes[2]=2; bytedes[2]=1; chandes[2]=4;
}
void chan_out(int value, unsigned *channel)
{
    if (channel!=file+2 && channel!=file+4) occam_fail("Occam invalid output channel");
    putchar(value);
}
void chan_in(int *value, unsigned *channel)
{
    if (channel!=file) occam_fail("Occam invalid input channel");
    *value=getchar();
}
void cbyte_in(char *value, unsigned *channel)
{ int v; chan_in(&v,channel); *value=v; }
void c_ba_out(char *values, unsigned count, unsigned *channel)
{ while (count--) chan_out(*values++,channel); }
void c_wa_out(int *values, unsigned count, unsigned *channel)
{ while (count--) chan_out(*values++,channel); }
void c_ba_in(char *values, unsigned count, unsigned *channel)
{ while (count--) cbyte_in(values++,channel); }
void c_wa_in(int *values, unsigned count, unsigned *channel)
{ while (count--) chan_in(values++,channel); }
void b_exit(int status) { _hlt(status); }
void occam_trap(int code) { occam_fail("Occam runtime trap"); }
void occam_copy(unsigned count, char *destination, char *source)
{
    if (destination>source) {
        destination+=count; source+=count;
        while (count--) *--destination=*--source;
    } else while (count--) *destination++=*source++;
}
