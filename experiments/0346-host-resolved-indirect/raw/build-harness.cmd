@echo off
rem BC5 experiment 0346: builds harness0346.cpp twice with MSVC (VS 18) — against main's backend sources and against
rem 0346's — into %OUT%\harness_main.exe and %OUT%\harness_0346.exe. Arguments: <main tree> <0346 tree> <out dir>,
rem each tree holding backend\ and gen\policy_tsv.hpp (the scratchpad layout the session prepared).
setlocal
set MAIN=%~1
set NEW=%~2
set OUT=%~3
set HERE=%~dp0
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
if not exist "%OUT%" mkdir "%OUT%"
cl /nologo /std:c++20 /EHsc /O1 /W3 /I "%MAIN%\backend\include" /I "%MAIN%\gen" "%HERE%harness0346.cpp" "%MAIN%\backend\src\policy.cpp" "%MAIN%\backend\src\indirect_check.cpp" "%MAIN%\backend\src\shadow_labels.cpp" /Fo"%OUT%\\" /Fe"%OUT%\harness_main.exe" || exit /b 1
cl /nologo /std:c++20 /EHsc /O1 /W3 /DBC5_HARNESS_0346 /I "%NEW%\backend\include" /I "%NEW%\gen" "%HERE%harness0346.cpp" "%NEW%\backend\src\policy.cpp" "%NEW%\backend\src\indirect_check.cpp" "%NEW%\backend\src\shadow_labels.cpp" "%NEW%\backend\src\host_indirect.cpp" /Fo"%OUT%\\" /Fe"%OUT%\harness_0346.exe" || exit /b 1
echo built %OUT%\harness_main.exe and %OUT%\harness_0346.exe
