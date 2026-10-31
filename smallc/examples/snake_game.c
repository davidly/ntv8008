/* Snake rules, separate from the terminal so they can be tested without input.
 * A 32 by 16 grid, byte occupancy map and circular buffer give constant-time
 * movement and collision checks. All indices are unsigned 16-bit values.
 */
unsigned int body[512];
char occupied[512];
unsigned int head, tail, length, direction, food, seed, erased;

newfood()
{
    seed = (seed * 109 + 89) & 511;
    food = seed;
    while (occupied[food]) food = (food + 1) & 511;
    return 0;
}

newgame()
{
    unsigned int i;
    for (i = 0; i < 512; ++i) occupied[i] = 0;
    for (i = 0; i < 4; ++i) {
        body[i] = 268 + i;
        occupied[body[i]] = 1;
    }
    head = 3;
    tail = 0;
    length = 4;
    direction = 0;
    seed = 7;
    newfood();
    return 0;
}

turn(key)
int key;
{
    unsigned int next;
    next = direction;
    if (key == 'd' || key == 'D') next = 0;
    if (key == 's' || key == 'S') next = 1;
    if (key == 'a' || key == 'A') next = 2;
    if (key == 'w' || key == 'W') next = 3;
    if (next != ((direction + 2) & 3)) direction = next;
    return 0;
}

/* Return 0 on collision, 1 on movement, 2 on food, 3 when the grid is full.
 * Entering the departing tail cell is legal unless the snake is growing.
 */
advance()
{
    unsigned int x, y, next, eating;
    x = body[head] & 31;
    y = body[head] >> 5;
    if (direction == 0) {
        if (x == 31) return 0;
        ++x;
    }
    if (direction == 1) {
        if (y == 15) return 0;
        ++y;
    }
    if (direction == 2) {
        if (x == 0) return 0;
        --x;
    }
    if (direction == 3) {
        if (y == 0) return 0;
        --y;
    }
    next = (y << 5) + x;
    eating = (next == food);
    if (occupied[next] && (eating || next != body[tail])) return 0;
    erased = 65535;
    if (eating) ++length;
    else {
        erased = body[tail];
        occupied[erased] = 0;
        tail = (tail + 1) & 511;
    }
    head = (head + 1) & 511;
    body[head] = next;
    occupied[next] = 1;
    if (length == 512) return 3;
    if (eating) {
        newfood();
        return 2;
    }
    return 1;
}
