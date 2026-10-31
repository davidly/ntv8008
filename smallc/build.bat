@echo off
setlocal
pushd "%~dp0.." || exit /b 1
if defined PYTHON goto python_ready
where py >nul 2>nul
if errorlevel 1 (set "PYTHON=python") else (set "PYTHON=py -3")
:python_ready
%PYTHON% smallc\build.py
if errorlevel 1 goto failed
call a08\m.bat
if errorlevel 1 goto failed
popd
exit /b 0
:failed
set "result=%errorlevel%"
popd
exit /b %result%
