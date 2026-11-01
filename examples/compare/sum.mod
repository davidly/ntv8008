MODULE SumTen;
FROM InOut IMPORT WriteCard, WriteLn;
VAR i, total: CARDINAL;
BEGIN
  total := 0;
  FOR i := 1 TO 10 DO total := total+i END;
  WriteCard(total, 1); WriteLn
END SumTen.
