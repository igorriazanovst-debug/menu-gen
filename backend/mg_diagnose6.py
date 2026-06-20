import requests, re, json
from bs4 import BeautifulSoup

URL = "https://www.russianfood.com/recipes/recipe.php?rid=165737"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

resp = requests.get(URL, headers=HEADERS, timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")

# ищем JSON в script-тегах
print("=== JSON в <script> ===")
for script in soup.find_all("script"):
    txt = script.string or ""
    # ищем ключевые слова
    if any(kw in txt for kw in ["ingredient", "ингредиент", "steps", "шаг", "nutrition", "калор", "recipe"]):
        print(f"--- script (len={len(txt)}) ---")
        print(txt[:800])
        print()

# ищем ajax/api url в скриптах
print("=== API URL в скриптах ===")
for script in soup.find_all("script"):
    txt = script.string or ""
    for m in re.finditer(r'["\']([^"\']*(?:api|ajax|json|data)[^"\']*)["\']', txt, re.I):
        u = m.group(1)
        if len(u) > 5:
            print(f"  {u}")

# dump первые 3000 символов body html (без скриптов/стилей)
print("\n=== HTML без скриптов (первые 3000) ===")
for tag in soup(["script","style","link","meta","noscript"]):
    tag.decompose()
print(soup.body.prettify()[:3000] if soup.body else "no body")
