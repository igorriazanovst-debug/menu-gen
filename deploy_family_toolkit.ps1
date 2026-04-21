# deploy_family_toolkit.ps1
param(
    [Parameter(Mandatory=$true)]
    [string]$SourceDir
)

$root = $PSScriptRoot

$files = @(
    @{ Src = "backend_family_serializers.py"; Dst = "backend\apps\family\serializers.py" },
    @{ Src = "backend_family_views.py";       Dst = "backend\apps\family\views.py" },
    @{ Src = "backend_family_urls.py";        Dst = "backend\apps\family\urls.py" },
    @{ Src = "family_bloc.dart";              Dst = "mobile\menugen_app\lib\features\family\bloc\family_bloc.dart" },
    @{ Src = "family_screen.dart";            Dst = "mobile\menugen_app\lib\features\family\screens\family_screen.dart" }
)

foreach ($f in $files) {
    $src = Join-Path $SourceDir $f.Src
    $dst = Join-Path $root $f.Dst

    if (-not (Test-Path $src)) {
        Write-Host "SKIP: $($f.Src)" -ForegroundColor Yellow
        continue
    }

    $dstDir = Split-Path $dst
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    }

    Copy-Item -Path $src -Destination $dst -Force
    Write-Host "OK: $($f.Dst)" -ForegroundColor Green
}

$partsToRemove = @(
    "mobile\menugen_app\lib\features\family\bloc\family_event.dart",
    "mobile\menugen_app\lib\features\family\bloc\family_state.dart"
)

foreach ($p in $partsToRemove) {
    $path = Join-Path $root $p
    if (Test-Path $path) {
        Remove-Item $path -Force
        Write-Host "REMOVED: $p" -ForegroundColor Cyan
    }
}

Write-Host "Done." -ForegroundColor Green
