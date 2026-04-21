"""
Запускать из корня проекта:
  python fix_recipe_photo.py
"""
import re, pathlib

FILE = pathlib.Path("web/menugen-web/src/pages/Recipes/RecipesPage.tsx")

src = FILE.read_text(encoding="utf-8")

# Убираем обрезку изображения в модальном окне
old = '<img src={recipe.image_url} alt={recipe.title} className="w-full h-56 object-cover rounded-t-2xl" />'
new = '<img src={recipe.image_url} alt={recipe.title} className="w-full object-contain rounded-t-2xl bg-gray-50" />'

if old not in src:
    print("WARN: строка не найдена, возможно уже исправлено или файл изменился")
else:
    src = src.replace(old, new)
    FILE.write_text(src, encoding="utf-8")
    print("OK: изображение в модальном окне исправлено")
