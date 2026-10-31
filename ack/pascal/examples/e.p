program e(output);
{ Decimal spigot: 200 working digits produce 192 output digits. }
const digits = 200; lastdigit = 199;
var
  a: packed array[0..lastdigit] of 0..255;
  high, n, x: integer;
begin
  x := 0;
  for n := 2 to digits-1 do a[n] := 1;
  a[0] := 0; a[1] := 2;
  high := digits;
  while high > 9 do begin
    high := high-1;
    n := high;
    while n <> 0 do begin
      a[n] := x mod n;
      x := 10*a[n-1] + x div n;
      n := n-1
    end;
    if x >= 10 then write(chr(ord('0') + x div 10));
    write(chr(ord('0') + x mod 10))
  end;
  writeln;
  writeln('done.')
end.
