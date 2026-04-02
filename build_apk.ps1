# build_apk.ps1
# Запуск: .\build_apk.ps1
# Результат: mobile\menugen_app\build\app\outputs\flutter-apk\app-debug.apk

param(
    [string]$ApiBaseUrl = ""
)

Set-Location "$PSScriptRoot"

$projectRoot = "C:\Temp\2026\menu-gen\menu-gen"
$mobileDir   = "$projectRoot\mobile\menugen_app"

if (-not $ApiBaseUrl) {
    $ip = Read-Host "Введи IP локальной машины (например 192.168.1.100)"
    $port = Read-Host "Порт бэкенда [8000]"
    if (-not $port) { $port = "8000" }
    $ApiBaseUrl = "http://${ip}:${port}/api/v1"
}

Write-Host "`nСборка APK с API: $ApiBaseUrl`n" -ForegroundColor Cyan

Set-Location $mobileDir

# Зависимости
flutter pub get

# Debug APK с dart-define (без хардкода URL в коде)
flutter build apk --debug `
    --dart-define=API_BASE_URL=$ApiBaseUrl

$apk = "$mobileDir\build\app\outputs\flutter-apk\app-debug.apk"

if (Test-Path $apk) {
    Write-Host "`n✅ APK готов: $apk" -ForegroundColor Green
    # Открыть папку в проводнике
    explorer.exe (Split-Path $apk)
} else {
    Write-Host "`n❌ Сборка не удалась. Проверь логи выше." -ForegroundColor Red
}