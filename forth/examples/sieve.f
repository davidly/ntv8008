( DX-FORTH odd-number sieve, with 8191 flags packed into 1024 bytes. )
( Packing leaves room for the interpreter and program in 16 KiB. )
DECIMAL
: FILL ( address count byte -- )
  ROT ROT
  BEGIN DUP WHILE >R 2DUP C! 1+ R> 1- REPEAT
  DROP 2DROP ;
8191 CONSTANT SIZE
VARIABLE FLAGS 1022 ALLOT
VARIABLE COUNT
: SIEVE
  10 0 DO
    FLAGS 1024 255 FILL
    0 COUNT !
    SIZE 0 DO
      FLAGS I BIT@ IF
        I I + 3 + DUP I +
        BEGIN DUP SIZE < WHILE FLAGS OVER BITCLR OVER + REPEAT
        DROP DROP 1 COUNT +!
      THEN
    LOOP
  LOOP
  ." count of primes: " COUNT @ . CR
  ." 10 iterations" CR ;
SIEVE BYE
