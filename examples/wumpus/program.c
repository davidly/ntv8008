/* Hunt the Wumpus, adapted from davidly/dcc tests/wumpus.c.
 * Original and adaptation: Copyright (c) 2026 David Lee. MIT; see LICENSE.
 * One shared traditional-C source for SmallC-85 and ACK C on the 8008.
 */

#include <stdio.h>

#define RMCNT 20
#define TUNC  3
#define LOCC  6
#define ARRMX 5
#define ARRWS 5

#define NO  0
#define YES 1

#define EPLY 0
#define EWUM 1
#define EP1  2
#define EP2  3
#define EB1  4
#define EB2  5

#define TMOV 0
#define TSHO 1

#define OCON 0
#define OWIN 1
#define OLOS 2

unsigned char loc[LOCC], ini[LOCC];
int arr, cpu;
char input[32];
unsigned char prev[21], queue[21];
int path[ARRMX];

/*
 * Dodecahedron cave: cave[room*TUNC+tunnel] gives the destination.
 * Byte elements and a flat array work in both target C dialects.
 * Keep globals before all functions for the original SmallC frontend.
 *   room 0  (unused sentinel): 0  0  0
 *   room 1:  2  5  8
 *   ...
 *   room 20: 13 16 19
 */
unsigned char cave[63] = {
    0,  0,  0,
    2,  5,  8,
    1,  3, 10,
    2,  4, 12,
    3,  5, 14,
    1,  4,  6,
    5,  7, 15,
    6,  8, 17,
    1,  7,  9,
    8, 10, 18,
    2,  9, 11,
   10, 12, 19,
    3, 11, 13,
   12, 14, 20,
    4, 13, 15,
    6, 14, 16,
   15, 17, 20,
    7, 16, 18,
    9, 17, 19,
   11, 18, 20,
   13, 16, 19
};

unsigned int seed = 317;

prmt(s)
char *s;
{
    while (*s) putchar(*s++);
    return 0;
}

rnd16()
{
    seed = seed * 25173 + 13849;
    seed = seed & 0xffff; /* Explicit 16-bit wrap also for a host reference build. */
    return (seed >> 1) & 0x7fff;
}

rndrm()
{
    return (rnd16() % RMCNT) + 1;
}

rndix(n)
int n;
{
    if (n <= 0)
        return 0;
    return rnd16() % n;
}

copyloc(d, s, n)
char *d;
char *s;
int n;
{
    int i;

    for (i = 0; i < n; ++i)
        d[i] = s[i];

    return 0;
}

/* Read a bounded line, echoing keys. Drain excess characters and accept
 * backspace without exposing the input buffer to an overrun. */
rdlin()
{
    int count, ch, overflow;
    count = 0;
    overflow = 0;
    while (1) {
        ch = getchar();
        if (ch == '\n' || ch == '\r') break;
        if (ch == 8 || ch == 127) {
            if (count) {
                count--;
                prmt("\b \b");
            }
        } else if (count < 31) {
            input[count++] = ch;
            putchar(ch);
        } else overflow = 1;
    }
    input[count] = 0;
    if (overflow) { input[0] = 0; puts("LINE TOO LONG"); }
    putchar('\n');
    return 0;
}

rdchr()
{
    int i, ch;
    rdlin();
    i = 0;
    while (input[i] == ' ' || input[i] == 9) i++;
    ch = input[i];
    if (ch >= 'a' && ch <= 'z') ch = ch - 'a' + 'A';
    return ch;
}

/* Accept a whole unsigned decimal line, bounded before multiplying. */
rdnum()
{
    int i, value, got, valid, ch;
    while (1) {
        rdlin();
        i = 0;
        value = 0;
        got = 0;
        valid = 1;
        while (input[i] == ' ' || input[i] == 9) i++;
        while (input[i] >= '0' && input[i] <= '9') {
            ch = input[i++] - '0';
            if (value > 3276 || (value == 3276 && ch > 7)) valid = 0;
            if (valid) value = value * 10 + ch;
            got = 1;
        }
        while (input[i] == ' ' || input[i] == 9) i++;
        if (got && valid && input[i] == 0) return value;
        prmt("ENTER A NUMBER FROM 0 TO 32767: ");
    }
}

adjo(f, t)
int f;
int t;
{
    int i;

    for (i = 0; i < TUNC; ++i) {
        if (cave[f*TUNC+i] == t)
            return YES;
    }

    return NO;
}

dupck(v, n)
char *v;
int n;
{
    int i, j;

    for (i = 0; i < n; ++i)
        for (j = i + 1; j < n; ++j)
            if (v[i] == v[j])
                return YES;

    return NO;
}

inst()
{
    puts("HUNT THE WUMPUS: 20 ROOMS, EACH WITH THREE TUNNELS.");
    puts("MOVE TO AN ADJACENT ROOM OR SHOOT AN ARROW THROUGH 1-5 ROOMS.");
    puts("TWO PITS KILL; TWO BAT ROOMS CARRY YOU SOMEWHERE ELSE.");
    puts("NEARBY HAZARDS GIVE WARNINGS. FIVE ARROWS; HIT THE WUMPUS TO WIN.");
    puts("AN IMPOSSIBLE ARROW STEP CHOOSES A RANDOM TUNNEL.");
    puts("NO A-B-A IN YOUR ROOM LIST. HITTING YOURSELF LOSES.");
    puts("A MISSED SHOT OR A BUMP WAKES THE WUMPUS: HE MAY MOVE OR STAY.");
    puts("ENTER EACH ANSWER THEN RETURN. Q QUITS AT THE S-M-Q PROMPT.");
    return 0;
}

ginit()
{
    int i;

    do {
        for (i = 0; i < LOCC; ++i)
            loc[i] = rndrm();
    } while (dupck(loc, LOCC));

    copyloc(ini, loc, LOCC);
    arr = ARRWS;
    return 0;
}

gsame()
{
    copyloc(loc, ini, LOCC);
    arr = ARRWS;
    return 0;
}

warns()
{
    int rm, i, a;

    rm = loc[EPLY];

    for (i = 0; i < TUNC; ++i) {
        a = cave[rm*TUNC+i];
        if (a == loc[EWUM])
            prmt("I SMELL A WUMPUS!\n");
        if (a == loc[EP1] || a == loc[EP2])
            prmt("I FEEL A DRAFT!\n");
        if (a == loc[EB1] || a == loc[EB2])
            prmt("BATS NEARBY!\n");
    }

    return 0;
}

stats()
{
    int rm;

    rm = loc[EPLY];
    prmt("\n");
    warns();
    prmt("YOU ARE IN ROOM ");
    putu(rm);
    prmt("\n");
    prmt("TUNNELS LEAD TO ");
    putu(cave[rm*TUNC+0]);
    prmt(", ");
    putu(cave[rm*TUNC+1]);
    prmt(", AND ");
    putu(cave[rm*TUNC+2]);
    prmt("\n");
    prmt("ARROWS LEFT: ");
    putu(arr);
    prmt("\n");
    prmt("\n");
    return 0;
}

wwak()
{
    int mv, wr;

    mv = rndix(4);
    if (mv < 3) {
        wr = loc[EWUM];
        loc[EWUM] = cave[wr*TUNC+mv];
    }

    if (loc[EWUM] == loc[EPLY]) {
        prmt("TSK TSK TSK - WUMPUS GOT YOU!\n");
        return OLOS;
    }

    return OCON;
}

presv()
{
    int rm;

    for (;;) {
        rm = loc[EPLY];

        if (rm == loc[EWUM]) {
            prmt("... OOPS! BUMPED A WUMPUS!\n");
            return wwak();
        }

        if (rm == loc[EP1] || rm == loc[EP2]) {
            prmt("YYYIIIIEEEE . . . FELL IN PIT\n");
            return OLOS;
        }

        if (rm == loc[EB1] || rm == loc[EB2]) {
            prmt("ZAP--SUPER BAT SNATCH! ELSEWHEREVILLE FOR YOU!\n");
            loc[EPLY] = rndrm();
            continue;
        }

        return OCON;
    }
}

pact()
{
    int ch;

    for (;;) {
        prmt("SHOOT, MOVE, OR QUIT (S-M-Q) ");
        ch = rdchr();
        if (ch == 'Q') return 2;
        if (ch == 'S')
            return TSHO;
        if (ch == 'M')
            return TMOV;
    }
}

movto(dst)
int dst;
{
    loc[EPLY] = dst;
    return presv();
}

pmove()
{
    int dst;

    for (;;) {
        prmt("WHERE TO ");
        dst = rdnum();

        if (dst < 1 || dst > RMCNT) {
            prmt("NOT POSSIBLE -\n");
            continue;
        }

        if (!adjo(loc[EPLY], dst)) {
            prmt("NOT POSSIBLE -\n");
            continue;
        }

        break;
    }

    return movto(dst);
}

plen()
{
    int n;

    for (;;) {
        prmt("NO. OF ROOMS (1-5) ");
        n = rdnum();
        if (n >= 1 && n <= ARRMX)
            return n;
    }
}

ppath(pth, len)
int *pth;
int len;
{
    int i;

    for (i = 0; i < len; ++i) {
        for (;;) {
            prmt("ROOM #");
            putu(i + 1);
            prmt(" ");
            pth[i] = rdnum();

            if (pth[i] < 1 || pth[i] > RMCNT)
                continue;

            if (i >= 2 && pth[i] == pth[i - 2]) {
                prmt("ARROWS AREN'T THAT CROOKED - TRY ANOTHER ROOM\n");
                    continue;
            }

            break;
        }
    }

    return 0;
}

ashot(pth, len)
int *pth;
int len;
{
    int ar, i;

    ar = loc[EPLY];

    for (i = 0; i < len; ++i) {
        if (adjo(ar, pth[i]))
            ar = pth[i];
        else
            ar = cave[ar*TUNC+rndix(TUNC)];

        if (ar == loc[EWUM]) {
            prmt("AHA! YOU GOT THE WUMPUS!\n");
            return OWIN;
        }

        if (ar == loc[EPLY]) {
            prmt("OUCH! ARROW GOT YOU!\n");
            arr = arr - 1;
            return OLOS;
        }
    }

    arr = arr - 1;
    prmt("MISSED\n");

    if (arr <= 0) {
        prmt("YOU RAN OUT OF ARROWS!\n");
        return OLOS;
    }

    return wwak();
}

pshot()
{
    int pth[ARRMX];
    int len;

    len = plen();
    ppath(pth, len);
    return ashot(pth, len);
}

pins()
{
    prmt("INSTRUCTIONS (Y-N) ");
    return (rdchr() != 'N');
}


/* The cave diameter is five, so a shortest shot always fits one arrow.
 * Computer mode knows all hazard locations, just like the source's -c mode. */
cturn()
{
    int head, tail, room, i, next, count;
    for (i = 0; i <= RMCNT; i++) prev[i] = 0;
    head = 0;
    tail = 1;
    queue[0] = loc[EPLY];
    prev[loc[EPLY]] = loc[EPLY];
    while (head < tail && prev[loc[EWUM]] == 0) {
        room = queue[head++];
        for (i = 0; i < TUNC; i++) {
            next = cave[room*TUNC+i];
            if (prev[next] == 0) {
                prev[next] = room;
                queue[tail++] = next;
            }
        }
    }
    count = 0;
    room = loc[EWUM];
    while (room != loc[EPLY]) {
        count++;
        room = prev[room];
    }
    room = loc[EWUM];
    for (i = count-1; i >= 0; i--) {
        path[i] = room;
        room = prev[room];
    }
    puts("COMPUTER CHOOSES: SHOOT");
    prmt("COMPUTER ARROW:");
    for (i = 0; i < count; i++) {
        putchar(' ');
        putu(path[i]);
    }
    putchar('\n');
    return ashot(path, count);
}

main()
{
    int out, act, answer;
    puts("HUNT THE WUMPUS - 8008");
    prmt("HUMAN OR COMPUTER (H-C, Q QUITS) ");
    answer = rdchr();
    if (answer == 'Q') return 0;
    cpu = (answer == 'C');
    prmt("SEED (1-32767, TRY 317) ");
    seed = rdnum();
    if (seed == 0) seed = 317;
    ginit();
    if (!cpu && pins()) inst();
    while (1) {
        out = OCON;
        puts("HUNT THE WUMPUS");
        while (out == OCON) {
            stats();
            if (cpu) out = cturn();
            else {
                act = pact();
                if (act == 2) return 0;
                if (act == TMOV) out = pmove();
                else out = pshot();
            }
        }
        if (out == OWIN) puts("HEE HEE HEE - THE WUMPUS'LL GETCHA NEXT TIME!!");
        else puts("HA HA HA - YOU LOSE!");
        if (cpu) return 0;
        prmt("SAME SET-UP (Y), NEW (N), OR QUIT (Q) ");
        answer = rdchr();
        if (answer == 'Q') return 0;
        if (answer == 'Y') gsame();
        else ginit();
    }
}
