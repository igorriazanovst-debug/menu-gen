"""
Копирует RecipesPage.tsx в нужную папку проекта.
Запускать из корня проекта:
  python apply_recipes_page.py
"""
import pathlib, shutil

ROOT = pathlib.Path(__file__).parent
SRC  = ROOT / "RecipesPage.tsx"
DST  = ROOT / "web" / "menugen-web" / "src" / "pages" / "Recipes" / "RecipesPage.tsx"

if not SRC.exists():
    print(f"ERROR: {SRC} не найден — положи RecipesPage.tsx рядом со скриптом")
    raise SystemExit(1)

shutil.copy2(SRC, DST)
print(f"OK: {DST.relative_to(ROOT)}")
