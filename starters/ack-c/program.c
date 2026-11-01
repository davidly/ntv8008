#include <stdio.h>

/* Four byte-sized array elements. Check the index before using it. */
unsigned char squares[4] = { 0, 1, 4, 9 };

int main(void)
{
    int key;

    puts("8008 SQUARE TABLE");
    puts("Choose 0..3:");
    key = getchar();
    putchar(key);
    putchar('\n');
    if (key < '0' || key > '3') {
        puts("USE A DIGIT FROM 0 TO 3.");
        return 0;
    }
    puts("SQUARE =");
    putu(squares[key - '0']);
    putchar('\n');
    return 0;
}
