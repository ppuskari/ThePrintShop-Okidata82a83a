param(
    [string]$OutputDir = "build-runtime",
    [string]$Merlin32 = "",
    [string]$BaseDisk = ""
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

$RepoRoot = Split-Path -Parent $PSScriptRoot
$OutPath = Join-Path $RepoRoot $OutputDir
New-Item -ItemType Directory -Force -Path $OutPath | Out-Null
$OutPath = (Resolve-Path $OutPath).Path

if ($Merlin32) {
    $MerlinExe = (Resolve-Path $Merlin32).Path
}
else {
    $Found = Get-Command merlin32.exe -ErrorAction SilentlyContinue
    if (-not $Found) {
        $Found = Get-Command merlin32 -ErrorAction SilentlyContinue
    }

    if ($Found) {
        $MerlinExe = $Found.Source
    }
    else {
        $ToolsRoot = Join-Path $OutPath "_tools"
        $MerlinRoot = Join-Path $ToolsRoot "merlin32-v1.1.10"
        $MerlinZip = Join-Path $ToolsRoot "merlin32-v1.1.10.zip"
        New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null

        if (-not (Test-Path $MerlinZip)) {
            Write-Host "Downloading Merlin32 v1.1.10..."
            $Uri = "https://github.com/digarok/merlin32/releases/download/v1.1.10/merlin32-windows-latest-v1.1.10.zip"
            Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $MerlinZip
        }

        New-Item -ItemType Directory -Force -Path $MerlinRoot | Out-Null
        Expand-Archive -Path $MerlinZip -DestinationPath $MerlinRoot -Force

        $Exe = Get-ChildItem -Path $MerlinRoot -Recurse -Filter merlin32.exe |
            Select-Object -First 1
        if (-not $Exe) {
            throw "Could not locate merlin32.exe in the downloaded release."
        }
        $MerlinExe = $Exe.FullName
    }
}

Write-Host "Using Merlin32: $MerlinExe"
Write-Host ""

Push-Location $RepoRoot
try {
    Write-Host "Running R31 regression tests..."
    Invoke-Checked {
        py -3 -m unittest discover -s tests -v
    } "Regression tests"

    Write-Host ""
    Write-Host "Preparing original-control and OkiGraph assembly sources..."
    Invoke-Checked {
        py -3 tools\prepare_merlin32_build.py --output-dir $OutPath
    } "Source preparation"

    Write-Host ""
    Write-Host "Assembling original controls and OkiGraph overlays..."
    Push-Location $OutPath
    try {
        foreach ($Source in @(
            "PRCOMS.ORIG.BUILD.S",
            "PRCOMS.OKI.BUILD.S",
            "MENUS7.ORIG.BUILD.S",
            "MENUS7.OKI.BUILD.S",
            "GCDRAW.ORIG.BUILD.S",
            "GCDRAW.OKI.BUILD.S",
            "MENUS3.ORIG.BUILD.S",
            "MENUS3.OKI.BUILD.S",
            "MENUS4.ORIG.BUILD.S",
            "MENUS4.OKI.BUILD.S",
            "LHDRAW.ORIG.BUILD.S",
            "LHDRAW.OKI.BUILD.S"
        )) {
            Write-Host "  $Source"
            & $MerlinExe $Source
            if ($LASTEXITCODE -ne 0) {
                throw "Merlin32 failed for $Source with exit code $LASTEXITCODE"
            }
        }
    }
    finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "Validating compiled overlays against known-good hashes..."
    Invoke-Checked {
        py -3 tools\validate_overlay_build.py --build-dir $OutPath
    } "Overlay validation"

    $Runtime = Join-Path $OutPath "PrintShop-Okidata82a83a-OkiGraphI.dsk"
    $Prcoms = Join-Path $OutPath "PRCOMS.OKI"
    $Menus7 = Join-Path $OutPath "MENUS7.OKI"
    $Menus3 = Join-Path $OutPath "MENUS3.OKI"
    $Menus4 = Join-Path $OutPath "MENUS4.OKI"
    $Gcdraw = Join-Path $OutPath "GCDRAW.OKI"
    $Lhdraw = Join-Path $OutPath "LHDRAW.OKI"

    Write-Host ""
    Write-Host "Constructing runnable Print Shop DOS disk..."
    $DiskArgs = @(
        "tools\build_runtime_disk.py",
        "--prcoms", $Prcoms,
        "--menus7", $Menus7,
        "--menus3", $Menus3,
        "--menus4", $Menus4,
        "--gcdraw", $Gcdraw,
        "--lhdraw", $Lhdraw,
        "--output", $Runtime
    )
    if ($BaseDisk) {
        $BasePath = (Resolve-Path $BaseDisk).Path
        $DiskArgs += @("--base-disk", $BasePath)
    }
    Invoke-Checked {
        & py -3 @DiskArgs
    } "Runtime disk build"

    Write-Host ""
    Write-Host "PASS - runnable image created:"
    Write-Host "  $Runtime"
    $Hash = Get-FileHash -Algorithm SHA256 $Runtime
    Write-Host "  SHA256 $($Hash.Hash.ToLowerInvariant())"
}
finally {
    Pop-Location
}
