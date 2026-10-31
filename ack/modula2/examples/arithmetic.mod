MODULE Arithmetic;
FROM InOut IMPORT WriteInt, WriteString, WriteLn;
VAR checks,x: INTEGER; cells: ARRAY [-1..1] OF INTEGER;
PROCEDURE Check(ok: BOOLEAN);
BEGIN IF ok THEN INC(checks) ELSE WriteString('FAIL'); WriteLn END END Check;
PROCEDURE Factorial(n: INTEGER): INTEGER;
BEGIN IF n=0 THEN RETURN 1 ELSE RETURN n*Factorial(n-1) END END Factorial;
PROCEDURE Outer(VAR a: INTEGER);
VAR b: INTEGER;
  PROCEDURE Inner(n: INTEGER);
  BEGIN a:=a+b+n; INC(b) END Inner;
BEGIN b:=2; Inner(4); Inner(4) END Outer;
BEGIN
  checks:=0; x:=17;
  Check(x+5=22); Check(x-20=-3); Check(x*5=85);
  Check(x DIV 5=3); Check(x MOD 5=2);
  Check(Factorial(6)=720);
  cells[-1]:=-8; cells[0]:=3; cells[1]:=14;
  Check(cells[-1]+cells[0]+cells[1]=9);
  x:=10; Outer(x); Check(x=23);
  WriteInt(checks,1); WriteString(' checks'); WriteLn
END Arithmetic.
