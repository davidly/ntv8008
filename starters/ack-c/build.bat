@echo off
setlocal
set "repo=%~dp0..\.."
pushd "%~dp0" || exit /b 1
if defined PYTHON goto python_ready
where py >nul 2>nul
if errorlevel 1 (set "PYTHON=python") else (set "PYTHON=py -3")
:python_ready
if not exist build mkdir build
if errorlevel 1 goto done
%PYTHON% "%repo%\ack\compile.py" program.c -o build\program.hex --assembly build\program.asm
:done
set "result=%errorlevel%"
popd
exit /b %result%
