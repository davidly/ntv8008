@echo off
setlocal
pushd "%~dp0.." || exit /b 1
if defined PYTHON goto ready
where py >nul 2>nul
if errorlevel 1 (set "PYTHON=python") else (set "PYTHON=py -3")
:ready
%PYTHON% tools\dependencies.py a08
set "result=%errorlevel%"
popd
exit /b %result%
