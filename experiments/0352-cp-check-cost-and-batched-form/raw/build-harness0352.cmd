@echo off
rem BC5 experiment 0352: builds harness0352.cpp with MSVC (VS 18) against this branch's backend sources into
rem %OUT%\harness_0352.exe (the 0346 harness plus --split). Arguments: <backend tree> <gen dir with policy_tsv.hpp> <out dir>.
setlocal
set TREE=%~1
set GEN=%~2
set OUT=%~3
set HERE=%~dp0
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
if not exist "%OUT%" mkdir "%OUT%"
cl /nologo /std:c++20 /EHsc /O1 /W3 /DBC5_HARNESS_0346 /I "%TREE%\include" /I "%GEN%" "%HERE%harness0352.cpp" "%TREE%\src\policy.cpp" "%TREE%\src\indirect_check.cpp" "%TREE%\src\shadow_labels.cpp" "%TREE%\src\host_indirect.cpp" "%TREE%\src\ib_split.cpp" /Fo"%OUT%\\" /Fe"%OUT%\harness_0352.exe" || exit /b 1
echo built %OUT%\harness_0352.exe
