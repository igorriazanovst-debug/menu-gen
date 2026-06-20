import requests, re

URL = "https://www.russianfood.com/recipes/recipe.php?rid=165737"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

html = requests.get(URL, headers=HEADERS, timeout=15).text

# ищем блоки вокруг ключевых слов
for kw in ["ингредиент", "состав", "порци", "грамм", "мин.", "шаг", "приготов"]:
    idx = html.lower().find(kw)
    if idx >= 0:
        snippet = html[max(0,idx-100):idx+300]
        # убираем теги для читаемости
        snippet_clean = re.sub(r'<[^>]+>', ' ', snippet).strip()
        print(f"[{kw}] pos={idx}:")
        print(f"  {snippet_clean[:200]}")
        print()
