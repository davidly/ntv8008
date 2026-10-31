/* ANSI terminal Snake. Run: ntv8008 -s:500000 smallc/examples/snake.hex
 * WASD steers, Q quits. Needs 34 columns by 23 rows. No host clock is used:
 * waitkey(40) plus game/drawing work gives about five moves/second at 500 kHz.
 */
#include <stdio.h>
#include "snake_game.c"

/* Screen coordinates are at most two decimal digits; avoid general division. */
coordinate(n)
unsigned int n;
{
    if (n >= 30) { putchar('3'); n = n - 30; }
    else if (n >= 20) { putchar('2'); n = n - 20; }
    else if (n >= 10) { putchar('1'); n = n - 10; }
    putchar('0' + n);
    return 0;
}

cursor(x, y)
unsigned int x, y;
{
    putchar(27); putchar('[');
    coordinate(y + 1); putchar(';'); coordinate(x + 1); putchar('H');
    return 0;
}

cell(position, ch)
unsigned int position;
int ch;
{
    cursor((position & 31) + 1, (position >> 5) + 3);
    putchar(ch);
    return 0;
}

score()
{
    cursor(0, 1);
    putchar('S'); putchar('c'); putchar('o'); putchar('r'); putchar('e');
    putchar(':'); putchar(' '); putu(length - 4);
    return 0;
}

screen()
{
    unsigned int i;
    putchar(27); putchar('['); putchar('2'); putchar('J');
    cursor(0, 0);
    puts("8008 SNAKE - WASD moves, Q quits");
    score();
    cursor(0, 2);
    for (i = 0; i < 34; ++i) putchar('#');
    cursor(0, 19);
    for (i = 0; i < 34; ++i) putchar('#');
    for (i = 3; i < 19; ++i) {
        cursor(0, i); putchar('#');
        cursor(33, i); putchar('#');
    }
    for (i = 0; i < 4; ++i) cell(body[i], 'O');
    cell(food, '*');
    return 0;
}

main()
{
    int key, result;
    newgame();
    screen();
    result = 1;
    while (result) {
        key = waitkey(40);
        if (key == 'q' || key == 'Q') break;
        turn(key);
        result = advance();
        if (result) {
            if (erased != 65535) cell(erased, ' ');
            cell(body[head], 'O');
            if (result >= 2) {
                if (result == 2) cell(food, '*');
                score();
            }
            if (result == 3) break;
        }
    }
    cursor(0, 21);
    if (result == 3) puts("You filled the board!");
    else if (result == 0) puts("Game over!");
    else puts("Bye!");
    return 0;
}
