param([ValidateSet('serve','test','demo')][string]$Action = 'serve')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path '.venv\phase3-installed')) {
    & $python -m pip install -r requirements-phase3.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    New-Item '.venv\phase3-installed' -ItemType File | Out-Null
}
$env:PYTHONPATH = "$PSScriptRoot;$PSScriptRoot\backend\src;$PSScriptRoot\phase1_compat\m2"
$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
switch ($Action) {
    'serve' { & $python scripts/run_local.py }
    'test' { & $python -m pytest -q tests_phase2 tests_phase3 }
    'demo' { & $python scripts/demo.py --state state-demo }
}
exit $LASTEXITCODE
