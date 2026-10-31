MODULE E;
FROM InOut IMPORT Write, WriteString, WriteLn;
VAR a: ARRAY [0..199] OF CHAR;
    high,n,x: CARDINAL;
BEGIN
  x:=0;
  FOR n:=2 TO 199 DO a[n]:=CHR(1) END;
  a[0]:=CHR(0); a[1]:=CHR(2); high:=200;
  WHILE high>9 DO
    DEC(high); n:=high;
    WHILE n#0 DO
      a[n]:=CHR(x MOD n);
      x:=10*ORD(a[n-1])+x DIV n;
      DEC(n)
    END;
    IF x>=10 THEN Write(CHR(ORD('0')+x DIV 10)) END;
    Write(CHR(ORD('0')+x MOD 10))
  END;
  WriteLn; WriteString('done.'); WriteLn
END E.
