program arithmetic(output);
var checks, count, total: integer;
    a: packed array[-2..2] of 0..255;
    words: array[3..5] of integer;

procedure check(ok: boolean);
begin
  if ok then checks:=checks+1 else writeln('FAIL')
end;

procedure add(var n: integer; amount: integer);
begin n:=n+amount end;

function deep(n: integer): integer;
var local: integer;
  function inner(extra: integer): integer;
  begin inner:=n+local+extra end;
begin
  local:=2;
  if n=0 then deep:=0
  else deep:=inner(3)+deep(n-1)
end;

begin
  checks:=0; count:=0;
  for total:=-2 to 2 do a[total]:=total+200;
  check(a[-2]=198); check(a[2]=202);
  words[3]:=-300; words[4]:=400; words[5]:=500;
  check(words[3]+words[4]+words[5]=600);
  check(deep(20)=310);
  add(count,17); check(count=17);
  total:=-17;
  check((total div 5)=-3); check(((total mod 5)=3) and (((-17) mod 5)=3));
  check(abs(-123)=123); check(sqr(123)=15129);
  total:=0;
  repeat total:=total+1 until total=3;
  check(total=3);
  while total>0 do total:=total-1;
  check(total=0);
  if odd(7) then count:=count+1;
  check(count=18);
  check(ord(chr(65))=65);
  writeln(checks:1,' checks')
end.
