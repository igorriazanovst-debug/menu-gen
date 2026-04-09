# build_apk.ps1
param([string]$ApiBaseUrl = "")

$projectRoot = "C:\Temp\2026\menu-gen\menu-gen"
$mobileDir   = "$projectRoot\mobile\menugen_app"

if (-not $ApiBaseUrl) {
    $ip = Read-Host "Enter local machine IP (e.g. 192.168.1.100)"
    $port = Read-Host "Backend port [8000]"
    if (-not $port) { $port = "8000" }
    $ApiBaseUrl = "http://${ip}:${port}/api/v1"
}

Write-Host "`nBuilding APK with API: $ApiBaseUrl`n" -ForegroundColor Cyan

Set-Location $mobileDir
flutter pub get
flutter build apk --debug --dart-define=API_BASE_URL=$ApiBaseUrl

$apk = "$mobileDir\build\app\outputs\flutter-apk\app-debug.apk"
if (Test-Path $apk) {
    Write-Host "`nAPK ready: $apk" -ForegroundColor Green
    explorer.exe (Split-Path $apk)
} else {
    Write-Host "`nBuild failed. Check logs above." -ForegroundColor Red
}
