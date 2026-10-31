@echo off
setlocal
pushd "%~dp0" || exit /b 1
cl /nologo /std:c++14 /EHsc /O2 /GL /W4 /D_CRT_SECURE_NO_WARNINGS ntv8008.cxx i8008.cxx /Fe:ntv8008.exe /link /LTCG
set "result=%errorlevel%"
popd
exit /b %result%
