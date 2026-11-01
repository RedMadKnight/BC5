@echo off
rem BC5 experiment 0390: build harness0390.cpp with Visual Studio 2026's clang-cl and AddressSanitizer.
rem usage: build0390.bat <dir with types.inc and queue.inc> <output exe>
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
set LLVM=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\Llvm\x64
"%LLVM%\bin\clang-cl.exe" --version | findstr /b "clang"
"%LLVM%\bin\clang-cl.exe" /nologo /std:c++20 /EHsc /Zi /O1 /MD /fsanitize=address /W3 /D_CRT_SECURE_NO_WARNINGS -Wno-unused-function -Wno-format ^
  /I"%~1" /Fo"%~dp2\" /Fd"%~dp2\" /Fe"%~2" "%~dp0harness0390.cpp"
