/* Ascending alpha-beta minimax: 6493 nodes for three opening positions. */
#include <stdio.h>
static unsigned char board[9];
static unsigned moves;
static int minmax(unsigned char alpha, unsigned char beta, unsigned char depth, unsigned char move)
{
    unsigned char pos, value, piece, score;
    ++moves;
    if (depth >= 4) {
        /* Inline last-move win dispatch to avoid a RAM-stack call. */
        piece = board[move];
        if (piece) {
            switch (move) {
            case 0:
                if ((piece == board[1] && piece == board[2]) ||
                    (piece == board[3] && piece == board[6]) ||
                    (piece == board[4] && piece == board[8]))
                    return piece == 1 ? 6 : 4;
                break;
            case 1:
                if ((piece == board[0] && piece == board[2]) ||
                    (piece == board[4] && piece == board[7]))
                    return piece == 1 ? 6 : 4;
                break;
            case 2:
                if ((piece == board[0] && piece == board[1]) ||
                    (piece == board[5] && piece == board[8]) ||
                    (piece == board[4] && piece == board[6]))
                    return piece == 1 ? 6 : 4;
                break;
            case 3:
                if ((piece == board[0] && piece == board[6]) ||
                    (piece == board[4] && piece == board[5]))
                    return piece == 1 ? 6 : 4;
                break;
            case 4:
                if ((piece == board[0] && piece == board[8]) ||
                    (piece == board[2] && piece == board[6]) ||
                    (piece == board[1] && piece == board[7]) ||
                    (piece == board[3] && piece == board[5]))
                    return piece == 1 ? 6 : 4;
                break;
            case 5:
                if ((piece == board[3] && piece == board[4]) ||
                    (piece == board[2] && piece == board[8]))
                    return piece == 1 ? 6 : 4;
                break;
            case 6:
                if ((piece == board[4] && piece == board[2]) ||
                    (piece == board[0] && piece == board[3]) ||
                    (piece == board[7] && piece == board[8]))
                    return piece == 1 ? 6 : 4;
                break;
            case 7:
                if ((piece == board[1] && piece == board[4]) ||
                    (piece == board[6] && piece == board[8]))
                    return piece == 1 ? 6 : 4;
                break;
            case 8:
                if ((piece == board[0] && piece == board[4]) ||
                    (piece == board[2] && piece == board[5]) ||
                    (piece == board[6] && piece == board[7]))
                    return piece == 1 ? 6 : 4;
                break;
            }
        }
        if (depth == 8) return 5;
    }
    piece = (depth & 1) ? 1 : 2;
    value = (depth & 1) ? 2 : 9;
    for (pos = 0; pos < 9; ++pos) {
        if (board[pos]) continue;
        board[pos] = piece;
        score = minmax(alpha, beta, depth + 1, pos);
        board[pos] = 0;
        if (piece == 1) {
            if (score > value) {
                value = score;
                if (value == 6 || value >= beta) return value;
                if (value > alpha) alpha = value;
            }
        } else {
            if (score < value) {
                value = score;
                if (value == 4 || value <= alpha) return value;
                if (value < beta) beta = value;
            }
        }
    }
    return value;
}
static int run(unsigned char move)
{
    unsigned char score;
    board[move] = 1;
    score = minmax(2, 9, 0, move);
    board[move] = 0;
    return score == 5;
}
int main(void)
{
    unsigned char iteration;
    for (iteration = 0; iteration < 10; ++iteration) {
        moves = 0;
        if (!run(0) || !run(1) || !run(4)) { puts("FAIL"); return 1; }
    }
    putu(moves); puts(" moves");
    puts("10 iterations");
    return 0;
}
