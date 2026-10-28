# BC5 experiment 0367: builds harness0367.cpp twice with MSVC (Visual Studio 18) on the laptop, against main's
# backend/src/full_state.cpp (<old full_state.cpp>, e.g. `git show origin/main:backend/src/full_state.cpp`) and against
# this tree's (candidate C1), into <out>\harness_main.exe and <out>\harness_0367.exe. The header is unchanged, so both
# take it from this tree. /O2 as a release build.
# usage: powershell -File build-harness0367.ps1 <repo tree> <old full_state.cpp> <out dir>
param([Parameter(Mandatory = $true)][string]$Tree, [Parameter(Mandatory = $true)][string]$Old, [Parameter(Mandatory = $true)][string]$Out)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$vcvars = 'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path $Out)) { New-Item -ItemType Directory -Path $Out | Out-Null }
New-Item -ItemType Directory -Force -Path "$Out\o1", "$Out\o2" | Out-Null
$common = '/nologo /std:c++20 /EHsc /O2 /W3'
$src = Join-Path $here 'harness0367.cpp'
$cmd1 = "cl $common /I `"$Tree\backend\include`" `"$src`" `"$Old`" /Fo`"$Out\o1\\`" /Fe`"$Out\harness_main.exe`""
$cmd2 = "cl $common /I `"$Tree\backend\include`" `"$src`" `"$Tree\backend\src\full_state.cpp`" /Fo`"$Out\o2\\`" /Fe`"$Out\harness_0367.exe`""
& cmd.exe /c "`"$vcvars`" >nul && $cmd1 && $cmd2"
if ($LASTEXITCODE -ne 0) { Write-Error "build failed ($LASTEXITCODE)"; exit 1 }
Write-Output "built $Out\harness_main.exe and $Out\harness_0367.exe"
