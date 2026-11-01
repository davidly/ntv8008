@echo off
setlocal
set "repo=%~dp0..\.."
pushd "%~dp0" || exit /b 1
if not exist build mkdir build
if errorlevel 1 goto done
"%repo%\a08\a08.exe" program.asm -obuild\program.hex
:done
set "result=%errorlevel%"
popd
exit /b %result%
