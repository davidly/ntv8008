DECIMAL
: FILL ( address count byte -- )
  ROT ROT
  BEGIN DUP WHILE >R 2DUP C! 1+ R> 1- REPEAT
  DROP 2DROP ;

200 CONSTANT DIGITS
VARIABLE ARRAY DIGITS ALLOT

: E
    ARRAY DIGITS 1 FILL
    0 ARRAY C!
    2 ARRAY 1+ C!

    DIGITS 0                    ( high x )
    BEGIN OVER 9 > WHILE
        SWAP 1- SWAP OVER       ( high x n )
        BEGIN DUP WHILE
            DUP >R /MOD         ( high remainder quotient; save n )
            SWAP R> SWAP OVER ARRAY + C!
            1- DUP ARRAY + C@ 10 * ROT + SWAP
                                ( high new-x n-1 )
        REPEAT
        DROP                    ( high x )
        DUP 10 /MOD             ( retain x for the next outer iteration )
        DUP IF 48 + EMIT ELSE DROP THEN
        48 + EMIT
    REPEAT
    2DROP CR
    ." done" CR ;

E BYE
