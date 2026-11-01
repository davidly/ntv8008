@echo off
setlocal
set "repo=%~dp0..\.."
pushd "%~dp0" || exit /b 1
"%repo%\ntv8008.exe" %* build\program.hex
set "result=%errorlevel%"
popd
exit /b %result%
