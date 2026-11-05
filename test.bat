@echo off
setlocal
pushd "%~dp0" || exit /b 1
set "repo=%CD%"
set "build_dir="
call m.bat
if errorlevel 1 goto failed
call a08\rebuild.bat hello.asm count.asm echo.asm sieve.asm e.asm ttt.asm robson.asm b8008.asm
if errorlevel 1 goto failed
if exist a08\forth.hex (
    call forth\rebuild.bat
    if errorlevel 1 goto failed
)
:choose_temp
set "build_dir=%TEMP%\i8008-test-%RANDOM%-%RANDOM%"
if exist "%build_dir%" goto choose_temp
mkdir "%build_dir%"
if errorlevel 1 goto failed
call :cpu_tests
if errorlevel 1 goto failed
rem Prefer the Python launcher; allow PYTHON to select another Python 3 command.
if defined PYTHON goto python_ready
where py >nul 2>nul
if errorlevel 1 (set "PYTHON=python") else (set "PYTHON=py -3")
:python_ready
%PYTHON% tests\run.py %*
if errorlevel 1 goto failed
set "result=0"
goto cleanup
:failed
set "result=%errorlevel%"
:cleanup
if defined build_dir if exist "%build_dir%" rmdir /s /q "%build_dir%"
popd
exit /b %result%
:cpu_tests
pushd "%build_dir%" || exit /b 1
cl /nologo /std:c++14 /EHsc /O2 /GL /W4 /D_CRT_SECURE_NO_WARNINGS /I"%repo%" "%repo%\tests\cpu.cxx" "%repo%\i8008.cxx" /Fe:cpu-test.exe /link /LTCG
if errorlevel 1 goto cpu_failed
cpu-test.exe cpu.log
if errorlevel 1 goto cpu_failed
popd
exit /b 0
:cpu_failed
set "cpu_result=%errorlevel%"
popd
exit /b %cpu_result%
