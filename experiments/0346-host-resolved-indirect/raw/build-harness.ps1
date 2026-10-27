# BC5 experiment 0346: builds harness0346.cpp twice with MSVC (Visual Studio 18) on the laptop: against main d0c2668's
# backend sources and against 0346's, into <out>\harness_main.exe and <out>\harness_0346.exe. Each tree holds backend\
# (the repository's directory) and gen\policy_tsv.hpp (policy_tsv.hpp.in with @BC5_POLICY_TSV@ replaced by
# backend\policy\pm4-policy.tsv, as CMake's configure_file does).
# usage: powershell -File build-harness.ps1 <main tree> <0346 tree> <out dir>
param([Parameter(Mandatory = $true)][string]$Main, [Parameter(Mandatory = $true)][string]$New, [Parameter(Mandatory = $true)][string]$Out)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$vcvars = 'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path $Out)) { New-Item -ItemType Directory -Path $Out | Out-Null }
$common = '/nologo /std:c++20 /EHsc /O1 /W3'
$src = Join-Path $here 'harness0346.cpp'
$cmd1 = "cl $common /I `"$Main\backend\include`" /I `"$Main\gen`" `"$src`" `"$Main\backend\src\policy.cpp`" `"$Main\backend\src\indirect_check.cpp`" `"$Main\backend\src\shadow_labels.cpp`" /Fo`"$Out\\`" /Fe`"$Out\harness_main.exe`""
$cmd2 = "cl $common /DBC5_HARNESS_0346 /I `"$New\backend\include`" /I `"$New\gen`" `"$src`" `"$New\backend\src\policy.cpp`" `"$New\backend\src\indirect_check.cpp`" `"$New\backend\src\shadow_labels.cpp`" `"$New\backend\src\host_indirect.cpp`" /Fo`"$Out\\`" /Fe`"$Out\harness_0346.exe`""
& cmd.exe /c "`"$vcvars`" >nul && $cmd1 && $cmd2"
if ($LASTEXITCODE -ne 0) { Write-Error "build failed ($LASTEXITCODE)"; exit 1 }
Write-Output "built $Out\harness_main.exe and $Out\harness_0346.exe"
