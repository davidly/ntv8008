program sieve(output);
{ Classic BYTE odd-number sieve: 8191 flags and ten passes. }
var
  flags: packed array[0..8190] of boolean;
  i, k, prime, count, iteration: integer;
begin
  count := 0;
  for iteration := 1 to 10 do begin
    for i := 0 to 8190 do flags[i] := true;
    count := 0;
    for i := 0 to 8190 do
      if flags[i] then begin
        prime := i+i+3;
        k := i+prime;
        while k <= 8190 do begin
          flags[k] := false;
          k := k+prime
        end;
        count := count+1
      end
  end;
  writeln(count:1, ' primes.')
end.
