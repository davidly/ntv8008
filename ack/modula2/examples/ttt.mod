MODULE Ttt;
FROM InOut IMPORT WriteInt, WriteString, WriteLn;
VAR board: ARRAY [0..8] OF INTEGER;
    moves,iteration: INTEGER; ok: BOOLEAN;

PROCEDURE Winner(move: INTEGER): INTEGER;
VAR p,result: INTEGER;
BEGIN
  p := board[move];
  result := 0;
  CASE move OF
    0: IF ((p=board[1]) AND (p=board[2])) OR
          ((p=board[3]) AND (p=board[6])) OR
          ((p=board[4]) AND (p=board[8])) THEN result:=p END
  | 1: IF ((p=board[0]) AND (p=board[2])) OR
          ((p=board[4]) AND (p=board[7])) THEN result:=p END
  | 2: IF ((p=board[0]) AND (p=board[1])) OR
          ((p=board[5]) AND (p=board[8])) OR
          ((p=board[4]) AND (p=board[6])) THEN result:=p END
  | 3: IF ((p=board[0]) AND (p=board[6])) OR
          ((p=board[4]) AND (p=board[5])) THEN result:=p END
  | 4: IF ((p=board[0]) AND (p=board[8])) OR
          ((p=board[2]) AND (p=board[6])) OR
          ((p=board[1]) AND (p=board[7])) OR
          ((p=board[3]) AND (p=board[5])) THEN result:=p END
  | 5: IF ((p=board[3]) AND (p=board[4])) OR
          ((p=board[2]) AND (p=board[8])) THEN result:=p END
  | 6: IF ((p=board[4]) AND (p=board[2])) OR
          ((p=board[0]) AND (p=board[3])) OR
          ((p=board[7]) AND (p=board[8])) THEN result:=p END
  | 7: IF ((p=board[1]) AND (p=board[4])) OR
          ((p=board[6]) AND (p=board[8])) THEN result:=p END
  | 8: IF ((p=board[0]) AND (p=board[4])) OR
          ((p=board[2]) AND (p=board[5])) OR
          ((p=board[6]) AND (p=board[7])) THEN result:=p END
  END;
  RETURN result
END Winner;


PROCEDURE Minmax(alpha,beta,depth,move: INTEGER): INTEGER;
VAR pos,value,piece,score: INTEGER; done: BOOLEAN;
BEGIN
  INC(moves); score:=0;
  IF depth>=4 THEN
    piece:=Winner(move);
    IF piece#0 THEN
      IF piece=1 THEN score:=6 ELSE score:=4 END
    ELSIF depth=8 THEN score:=5 END
  END;
  IF score#0 THEN RETURN score END;
  IF depth MOD 2=1 THEN piece:=1; value:=2
  ELSE piece:=2; value:=9 END;
  pos:=0; done:=FALSE;
  WHILE (pos<9) AND NOT done DO
    IF board[pos]=0 THEN
      board[pos]:=piece;
      score:=Minmax(alpha,beta,depth+1,pos);
      board[pos]:=0;
      IF piece=1 THEN
        IF score>value THEN
          value:=score;
          IF (value=6) OR (value>=beta) THEN done:=TRUE
          ELSIF value>alpha THEN alpha:=value END
        END
      ELSE
        IF score<value THEN
          value:=score;
          IF (value=4) OR (value<=alpha) THEN done:=TRUE
          ELSIF value<beta THEN beta:=value END
        END
      END
    END;
    INC(pos)
  END;
  RETURN value
END Minmax;

PROCEDURE Run(move: INTEGER): BOOLEAN;
VAR score: INTEGER;
BEGIN
  board[move]:=1; score:=Minmax(2,9,0,move); board[move]:=0;
  RETURN score=5
END Run;

BEGIN
  ok:=TRUE;
  FOR iteration:=1 TO 10 DO
    moves:=0;
    IF NOT Run(0) THEN ok:=FALSE END;
    IF NOT Run(1) THEN ok:=FALSE END;
    IF NOT Run(4) THEN ok:=FALSE END
  END;
  IF ok THEN
    WriteInt(moves,1); WriteString(' moves'); WriteLn;
    WriteString('10 iterations'); WriteLn
  ELSE WriteString('FAIL'); WriteLn END
END Ttt.
