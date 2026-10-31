@echo off
setlocal
pushd "%~dp0" || exit /b 1
call m.bat
if errorlevel 1 goto failed
if defined PYTHON goto python_ready
where py >nul 2>nul
if errorlevel 1 (set "PYTHON=python") else (set "PYTHON=py -3")
:python_ready
%PYTHON% tests\basic_benchmarks.py
:failed
set "result=%errorlevel%"
popd
exit /b %result%
