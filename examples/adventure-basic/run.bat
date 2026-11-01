@echo off
setlocal
set "repo=%~dp0..\.."
pushd "%~dp0" || exit /b 1
if not exist build mkdir build
if errorlevel 1 goto done
copy /b program.bas+input.txt build\session.bas >nul
if errorlevel 1 goto done
"%repo%\ntv8008.exe" %* -l:build\session.bas "%repo%\a08\b8008.hex"
:done
set "result=%errorlevel%"
popd
exit /b %result%
