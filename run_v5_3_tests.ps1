$ErrorActionPreference = 'Stop'
$tests = @(
    'tests/test_phase_v5_3_contract.py',
    'tests/test_phase_v5_3_installer.py',
    'tests/test_phase_v5_2_contract.py',
    'tests/test_phase_v5_2_installer.py',
    'tests/test_phase_v5_contract.py',
    'tests/test_phase_v4_contract.py',
    'tests/test_phase_v3_2_contract.py',
    'tests/test_phase_v3_1_contract.py',
    'tests/test_phase_v3_contract.py',
    'tests/test_phase_v2_contract.py',
    'tests/test_phase_v1_contract.py',
    'tests/test_qt_save_reorder_contract.py',
    'tests/test_reference_autoscroll.py'
)
foreach ($t in $tests) {
    if (!(Test-Path $t)) {
        Write-Host "SKIP missing: $t" -ForegroundColor Yellow
        continue
    }
    Write-Host "RUN: $t" -ForegroundColor Cyan
    python $t
    if ($LASTEXITCODE -ne 0) { throw "FAIL: $t ($LASTEXITCODE)" }
}
Write-Host 'All available source tests passed. Blender UI tests remain separate.' -ForegroundColor Green
