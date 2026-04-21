"""
Откат предыдущего фикса.
Запускать из корня проекта:
  python rollback_recipe_photo.py
"""
import pathlib

FILE = pathlib.Path("web/menugen-web/src/pages/Recipes/RecipesPage.tsx")

src = FILE.read_text(encoding="utf-8")

old = '<img src={recipe.image_url} alt={recipe.title} className="w-full max-h-72 object-contain rounded-t-2xl bg-gray-50" />'
new = '<img src={recipe.image_url} alt={recipe.title} className="w-full h-56 object-cover rounded-t-2xl" />'

if old not in src:
    print("WARN: строка не найдена — возможно откат уже выполнен")
else:
    src = src.replace(old, new)
    FILE.write_text(src, encoding="utf-8")
    print("OK: откат выполнен")
