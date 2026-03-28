#!/usr/bin/env pwsh
# deploy_specialist.ps1
# Копирует файлы кабинета специалиста в нужные папки проекта.
# Запускать из корня проекта: .\deploy_specialist.ps1
# Или с указанием пути к архиву: .\deploy_specialist.ps1 -Archive "C:\Downloads\specialist_stage5.tar.gz"

param(
    [string]$Archive = "specialist_stage5.tar.gz",
    [string]$ProjectRoot = $PSScriptRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Пути ────────────────────────────────────────────────────────────────────
$BackendDst = Join-Path $ProjectRoot "backend\apps\specialists"
$StoreDst   = Join-Path $ProjectRoot "web\menugen-web\src\store"
$PagesDst   = Join-Path $ProjectRoot "web\menugen-web\src\pages\specialist"

# ── Распаковка архива ────────────────────────────────────────────────────────
$TmpDir = Join-Path $env:TEMP "menugen_specialist_$(Get-Random)"
New-Item -ItemType Directory -Path $TmpDir | Out-Null

Write-Host "Распаковка $Archive ..."
tar -xzf $Archive -C $TmpDir
if ($LASTEXITCODE -ne 0) {
    Write-Error "Ошибка распаковки архива."
    exit 1
}

$BackendSrc  = Join-Path $TmpDir "specialist_backend"
$FrontendSrc = Join-Path $TmpDir "specialist_frontend"

# ── Бэкенд ───────────────────────────────────────────────────────────────────
Write-Host "`n[Backend] $BackendDst"

foreach ($file in @("serializers.py", "views.py", "urls.py")) {
    $src = Join-Path $BackendSrc $file
    $dst = Join-Path $BackendDst $file

    if (-not (Test-Path $src)) {
        Write-Warning "  Не найден: $src — пропуск."
        continue
    }

    if (Test-Path $dst) {
        $bak = "$dst.bak"
        Copy-Item $dst $bak -Force
        Write-Host "  BAK: $file.bak"
    }

    Copy-Item $src $dst -Force
    Write-Host "  OK : $file"
}

# ── React store ───────────────────────────────────────────────────────────────
Write-Host "`n[React/store] $StoreDst"
New-Item -ItemType Directory -Force -Path $StoreDst | Out-Null

$sliceSrc = Join-Path $FrontendSrc "specialistSlice.ts"
$sliceDst = Join-Path $StoreDst "specialistSlice.ts"

if (Test-Path $sliceSrc) {
    if (Test-Path $sliceDst) { Copy-Item $sliceDst "$sliceDst.bak" -Force; Write-Host "  BAK: specialistSlice.ts.bak" }
    Copy-Item $sliceSrc $sliceDst -Force
    Write-Host "  OK : specialistSlice.ts"
} else {
    Write-Warning "  Не найден: specialistSlice.ts"
}

# ── React pages ───────────────────────────────────────────────────────────────
Write-Host "`n[React/pages] $PagesDst"
New-Item -ItemType Directory -Force -Path $PagesDst | Out-Null

$pages = @(
    "SpecialistDashboardPage.tsx",
    "ClientDetailPage.tsx",
    "ClientMenuEditorPage.tsx",
    "RecommendationFormPage.tsx",
    "SpecialistRegisterPage.tsx"
)

foreach ($file in $pages) {
    $src = Join-Path $FrontendSrc $file
    $dst = Join-Path $PagesDst $file

    if (-not (Test-Path $src)) {
        Write-Warning "  Не найден: $src — пропуск."
        continue
    }

    if (Test-Path $dst) {
        Copy-Item $dst "$dst.bak" -Force
        Write-Host "  BAK: $file.bak"
    }

    Copy-Item $src $dst -Force
    Write-Host "  OK : $file"
}

# ── Cleanup ───────────────────────────────────────────────────────────────────
Remove-Item -Recurse -Force $TmpDir

# ── Итог ─────────────────────────────────────────────────────────────────────
Write-Host @"

────────────────────────────────────────────────────────
Готово. Теперь вручную:

1. backend\apps\specialists\urls.py уже заменён.
   Убедись что в backend\config\urls.py путь подключён:
     path("api/v1/specialists/", include("apps.specialists.urls")),

2. web\menugen-web\src\store\index.ts — добавить:
     import specialistReducer from "./specialistSlice";
     // в configureStore reducer:
     specialist: specialistReducer,

3. web\menugen-web\src\App.tsx — добавить маршруты:
     <Route path="/specialist" element={<SpecialistDashboardPage />} />
     <Route path="/specialist/register" element={<SpecialistRegisterPage />} />
     <Route path="/specialist/clients/:familyId" element={<ClientDetailPage />} />
     <Route path="/specialist/clients/:familyId/menus/:menuId" element={<ClientMenuEditorPage />} />
     <Route path="/specialist/clients/:familyId/recommendations/new" element={<RecommendationFormPage />} />

4. В Sidebar — ссылка /specialist (показывать если user — специалист).
────────────────────────────────────────────────────────
"@
