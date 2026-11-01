program ttt(output);
{ Ascending alpha-beta minimax: 6493 nodes across three opening positions. }
var
  board: packed array[0..8] of 0..2;
  moves, iteration: integer;
  ok: boolean;

function minmax(alpha,beta,depth,move: integer): integer;
var pos, value, piece, score: integer;
    done: boolean;
begin
  moves := moves+1;
  score := 0;
  if depth >= 4 then begin
    { Inline win dispatch; the last-move square is occupied. }
    piece := board[move];
    done := false;
    case move of
      0: if ((piece=board[1]) and (piece=board[2])) or
            ((piece=board[3]) and (piece=board[6])) or
            ((piece=board[4]) and (piece=board[8])) then done:=true;
      1: if ((piece=board[0]) and (piece=board[2])) or
            ((piece=board[4]) and (piece=board[7])) then done:=true;
      2: if ((piece=board[0]) and (piece=board[1])) or
            ((piece=board[5]) and (piece=board[8])) or
            ((piece=board[4]) and (piece=board[6])) then done:=true;
      3: if ((piece=board[0]) and (piece=board[6])) or
            ((piece=board[4]) and (piece=board[5])) then done:=true;
      4: if ((piece=board[0]) and (piece=board[8])) or
            ((piece=board[2]) and (piece=board[6])) or
            ((piece=board[1]) and (piece=board[7])) or
            ((piece=board[3]) and (piece=board[5])) then done:=true;
      5: if ((piece=board[3]) and (piece=board[4])) or
            ((piece=board[2]) and (piece=board[8])) then done:=true;
      6: if ((piece=board[4]) and (piece=board[2])) or
            ((piece=board[0]) and (piece=board[3])) or
            ((piece=board[7]) and (piece=board[8])) then done:=true;
      7: if ((piece=board[1]) and (piece=board[4])) or
            ((piece=board[6]) and (piece=board[8])) then done:=true;
      8: if ((piece=board[0]) and (piece=board[4])) or
            ((piece=board[2]) and (piece=board[5])) or
            ((piece=board[6]) and (piece=board[7])) then done:=true
    end;
    if done then begin
      if piece = 1 then score := 6 else score := 4
    end else if depth = 8 then score := 5
  end;
  if score <> 0 then minmax := score
  else begin
    if depth mod 2 = 1 then begin piece:=1; value:=2 end
    else begin piece:=2; value:=9 end;
    pos := 0; done := false;
    while (pos < 9) and not done do begin
      if board[pos] = 0 then begin
        board[pos] := piece;
        score := minmax(alpha,beta,depth+1,pos);
        board[pos] := 0;
        if piece = 1 then begin
          if score > value then begin
            value := score;
            if (value=6) or (value>=beta) then done:=true
            else if value > alpha then alpha:=value
          end
        end else begin
          if score < value then begin
            value := score;
            if (value=4) or (value<=alpha) then done:=true
            else if value < beta then beta:=value
          end
        end
      end;
      pos := pos+1
    end;
    minmax := value
  end
end;

function run(move: integer): boolean;
var score: integer;
begin
  board[move] := 1;
  score := minmax(2,9,0,move);
  board[move] := 0;
  run := score=5
end;

begin
  ok := true;
  for iteration := 1 to 10 do begin
    moves := 0;
    if not run(0) then ok:=false;
    if not run(1) then ok:=false;
    if not run(4) then ok:=false
  end;
  if ok then begin
    writeln(moves:1, ' moves');
    writeln('10 iterations')
  end else writeln('FAIL')
end.
