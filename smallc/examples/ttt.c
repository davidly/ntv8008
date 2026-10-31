/* Ascending alpha-beta minimax: 6493 nodes for three opening positions. */
#include <stdio.h>
static unsigned char board[9];
static unsigned int moves;
winner(move)
int move;
{
    int p;
    p = board[move];
    switch (move) {
    case 0: return ((p == board[1] && p == board[2]) ||
                    (p == board[3] && p == board[6]) ||
                    (p == board[4] && p == board[8])) ? p : 0;
    case 1: return ((p == board[0] && p == board[2]) ||
                    (p == board[4] && p == board[7])) ? p : 0;
    case 2: return ((p == board[0] && p == board[1]) ||
                    (p == board[5] && p == board[8]) ||
                    (p == board[4] && p == board[6])) ? p : 0;
    case 3: return ((p == board[0] && p == board[6]) ||
                    (p == board[4] && p == board[5])) ? p : 0;
    case 4: return ((p == board[0] && p == board[8]) ||
                    (p == board[2] && p == board[6]) ||
                    (p == board[1] && p == board[7]) ||
                    (p == board[3] && p == board[5])) ? p : 0;
    case 5: return ((p == board[3] && p == board[4]) ||
                    (p == board[2] && p == board[8])) ? p : 0;
    case 6: return ((p == board[4] && p == board[2]) ||
                    (p == board[0] && p == board[3]) ||
                    (p == board[7] && p == board[8])) ? p : 0;
    case 7: return ((p == board[1] && p == board[4]) ||
                    (p == board[6] && p == board[8])) ? p : 0;
    case 8: return ((p == board[0] && p == board[4]) ||
                    (p == board[2] && p == board[5]) ||
                    (p == board[6] && p == board[7])) ? p : 0;
    }
    return 0;
}
minmax(alpha, beta, depth, move)
int alpha;
int beta;
int depth;
int move;
{
    int pos, value, piece, score;
    ++moves;
    if (depth >= 4) {
        piece = winner(move);
        if (piece) return piece == 1 ? 6 : 4;
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
run(move)
int move;
{
    int score;
    board[move] = 1;
    score = minmax(2, 9, 0, move);
    board[move] = 0;
    return score == 5;
}
main()
{
    int iteration;
    for (iteration = 0; iteration < 10; ++iteration) {
        moves = 0;
        if (!run(0) || !run(1) || !run(4)) { puts("FAIL"); return 1; }
    }
    putu(moves); puts(" moves");
    puts("10 iterations");
    return 0;
}
