MODULE Sieve;
FROM InOut IMPORT WriteInt, WriteString, WriteLn;
VAR flags: ARRAY [0..8190] OF BOOLEAN;
    i,k,prime,count,iteration: INTEGER;
BEGIN
  FOR iteration:=1 TO 10 DO
    FOR i:=0 TO 8190 DO flags[i]:=TRUE END;
    count:=0;
    FOR i:=0 TO 8190 DO
      IF flags[i] THEN
        prime:=i+i+3; k:=i+prime;
        WHILE k<=8190 DO flags[k]:=FALSE; k:=k+prime END;
        INC(count)
      END
    END
  END;
  WriteInt(count,1); WriteString(' primes.'); WriteLn
END Sieve.
