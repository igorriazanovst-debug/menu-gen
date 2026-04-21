# Запускать из корня проекта: C:\Temp\2026\menu-gen\menu-gen
$file = "web\menugen-web\src\pages\Recipes\RecipesPage.tsx"

(Get-Content $file -Raw) -replace `
  'className="w-full h-56 object-cover rounded-t-2xl"', `
  'className="w-full max-h-72 object-contain rounded-t-2xl bg-gray-50"' `
| Set-Content $file -Encoding UTF8

Write-Host "Done: $file"
