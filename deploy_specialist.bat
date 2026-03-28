@echo off
setlocal enabledelayedexpansion

set ARCHIVE=%~1
if "%ARCHIVE%"=="" set ARCHIVE=specialist_stage5.tar.gz

set PROJECT_ROOT=%~dp0
if "%PROJECT_ROOT:~-1%"=="\" set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%

set BACKEND_DST=%PROJECT_ROOT%\backend\apps\specialists
set STORE_DST=%PROJECT_ROOT%\web\menugen-web\src\store
set PAGES_DST=%PROJECT_ROOT%\web\menugen-web\src\pages\specialist
set TMP_DIR=%TEMP%\menugen_%RANDOM%

echo Unpacking %ARCHIVE% ...
mkdir "%TMP_DIR%"
tar -xzf "%ARCHIVE%" -C "%TMP_DIR%"
if errorlevel 1 (
    echo ERROR: failed to unpack archive.
    exit /b 1
)

set BACKEND_SRC=%TMP_DIR%\specialist_backend
set FRONTEND_SRC=%TMP_DIR%\specialist_frontend

echo.
echo [Backend] %BACKEND_DST%

for %%F in (serializers.py views.py urls.py) do (
    if exist "%BACKEND_SRC%\%%F" (
        if exist "%BACKEND_DST%\%%F" (
            copy /Y "%BACKEND_DST%\%%F" "%BACKEND_DST%\%%F.bak" >nul
            echo   bak: %%F.bak
        )
        copy /Y "%BACKEND_SRC%\%%F" "%BACKEND_DST%\%%F" >nul
        echo   ok:  %%F
    ) else (
        echo   skip: %%F not found
    )
)

echo.
echo [React store] %STORE_DST%
if not exist "%STORE_DST%" mkdir "%STORE_DST%"

if exist "%FRONTEND_SRC%\specialistSlice.ts" (
    if exist "%STORE_DST%\specialistSlice.ts" (
        copy /Y "%STORE_DST%\specialistSlice.ts" "%STORE_DST%\specialistSlice.ts.bak" >nul
        echo   bak: specialistSlice.ts.bak
    )
    copy /Y "%FRONTEND_SRC%\specialistSlice.ts" "%STORE_DST%\specialistSlice.ts" >nul
    echo   ok:  specialistSlice.ts
) else (
    echo   skip: specialistSlice.ts not found
)

echo.
echo [React pages] %PAGES_DST%
if not exist "%PAGES_DST%" mkdir "%PAGES_DST%"

for %%F in (SpecialistDashboardPage.tsx ClientDetailPage.tsx ClientMenuEditorPage.tsx RecommendationFormPage.tsx SpecialistRegisterPage.tsx) do (
    if exist "%FRONTEND_SRC%\%%F" (
        if exist "%PAGES_DST%\%%F" (
            copy /Y "%PAGES_DST%\%%F" "%PAGES_DST%\%%F.bak" >nul
            echo   bak: %%F.bak
        )
        copy /Y "%FRONTEND_SRC%\%%F" "%PAGES_DST%\%%F" >nul
        echo   ok:  %%F
    ) else (
        echo   skip: %%F not found
    )
)

rmdir /S /Q "%TMP_DIR%"

echo.
echo Done.
echo.
echo Next steps (manual):
echo  1. backend\config\urls.py - check: path("api/v1/specialists/", include("apps.specialists.urls")),
echo  2. web\menugen-web\src\store\index.ts - add: specialist: specialistReducer,
echo  3. web\menugen-web\src\App.tsx - add routes /specialist/...
echo  4. Sidebar - add link /specialist

endlocal