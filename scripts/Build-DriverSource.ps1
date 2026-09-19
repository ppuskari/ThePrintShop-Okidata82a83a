param(
    [string]$OutputDir = "build"
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

Write-Host "Validating OkiGraph I driver model..."
Invoke-Checked {
    py -3 -m unittest discover -s tests -v
} "Driver regression tests"

Write-Host ""
Write-Host "Validating patch against the 1987 Print Shop v2 source..."
Invoke-Checked {
    py -3 tools\patch_printshop_source.py --check
} "Historical source patch check"

Write-Host ""
Write-Host "Generating patched decoded source in '$OutputDir'..."
Invoke-Checked {
    py -3 tools\patch_printshop_source.py --output-dir $OutputDir --output-disks $OutputDir
} "Patched source generation"

Write-Host ""
Write-Host "PASS"
Write-Host "  $OutputDir\PRCOMS.OKI.S"
Write-Host "  $OutputDir\MENUS7.OKI.S"
