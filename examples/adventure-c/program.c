#include <stdio.h>

/* Room 0: hall, 1: cellar with key, 2: locked exit.
   Commands are single digits: north, south, take, open, quit. */
unsigned char north[3] = { 2, 0, 2 };
unsigned char south[3] = { 1, 1, 0 };

main()
{
    int room, key, command;
    room = 0;
    key = 0;
    puts("THE THREE-ROOM ESCAPE");
    puts("1 NORTH, 2 SOUTH, 3 TAKE, 4 OPEN, 0 QUIT");
    while (1) {
        if (room == 0) puts("HALL");
        if (room == 1) puts("CELLAR");
        if (room == 2) puts("LOCKED DOOR");
        command = getchar();
        if (command == '0') { puts("GOODBYE"); return 0; }
        if (command == '1') room = north[room];
        else if (command == '2') room = south[room];
        else if (command == '3') {
            if (room == 1) { key = 1; puts("KEY TAKEN"); }
            else puts("NOTHING TO TAKE");
        } else if (command == '4') {
            if (room == 2 && key) { puts("YOU ESCAPED!"); return 0; }
            puts("YOU NEED THE KEY AT THE DOOR");
        } else if (command != '\n' && command != '\r') puts("USE 0 TO 4");
    }
}
