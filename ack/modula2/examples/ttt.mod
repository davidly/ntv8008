MODULE Ttt;
FROM InOut IMPORT WriteInt, WriteString, WriteLn;
VAR board: ARRAY [0..8] OF INTEGER;
    moves,iteration: INTEGER; ok: BOOLEAN;

PROCEDURE Minmax(alpha,beta,depth,move: INTEGER): INTEGER;
VAR pos,value,piece,score: INTEGER; done: BOOLEAN;
BEGIN
  INC(moves);
  IF depth>=4 THEN
    (* Inline win dispatch instead of a separate procedure call. *)
    piece:=board[move];
    IF piece#0 THEN
      CASE move OF
        0: IF ((piece=board[1]) AND (piece=board[2])) OR
              ((piece=board[3]) AND (piece=board[6])) OR
              ((piece=board[4]) AND (piece=board[8])) THEN
          IF piece=1 THEN RETURN 6 ELSE RETURN 4 END
        END
      | 1: IF ((piece=board[0]) AND (piece=board[2])) OR
              ((piece=board[4]) AND (piece=board[7])) THEN
          IF piece=1 THEN RETURN 6 ELSE RETURN 4 END
        END
      | 2: IF ((piece=board[0]) AND (piece=board[1])) OR
              ((piece=board[5]) AND (piece=board[8])) OR
              ((piece=board[4]) AND (piece=board[6])) THEN
          IF piece=1 THEN RETURN 6 ELSE RETURN 4 END
        END
      | 3: IF ((piece=board[0]) AND (piece=board[6])) OR
              ((piece=board[4]) AND (piece=board[5])) THEN
          IF piece=1 THEN RETURN 6 ELSE RETURN 4 END
        END
      | 4: IF ((piece=board[0]) AND (piece=board[8])) OR
              ((piece=board[2]) AND (piece=board[6])) OR
              ((piece=board[1]) AND (piece=board[7])) OR
              ((piece=board[3]) AND (piece=board[5])) THEN
          IF piece=1 THEN RETURN 6 ELSE RETURN 4 END
        END
      | 5: IF ((piece=board[3]) AND (piece=board[4])) OR
              ((piece=board[2]) AND (piece=board[8])) THEN
          IF piece=1 THEN RETURN 6 ELSE RETURN 4 END
        END
      | 6: IF ((piece=board[4]) AND (piece=board[2])) OR
              ((piece=board[0]) AND (piece=board[3])) OR
              ((piece=board[7]) AND (piece=board[8])) THEN
          IF piece=1 THEN RETURN 6 ELSE RETURN 4 END
        END
      | 7: IF ((piece=board[1]) AND (piece=board[4])) OR
              ((piece=board[6]) AND (piece=board[8])) THEN
          IF piece=1 THEN RETURN 6 ELSE RETURN 4 END
        END
      | 8: IF ((piece=board[0]) AND (piece=board[4])) OR
              ((piece=board[2]) AND (piece=board[5])) OR
              ((piece=board[6]) AND (piece=board[7])) THEN
          IF piece=1 THEN RETURN 6 ELSE RETURN 4 END
        END
      END
    END;
    IF depth=8 THEN RETURN 5 END
  END;
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
