import requests
from bs4 import BeautifulSoup

URL = "https://www.russianfood.com/recipes/recipe.php?rid=165737"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

resp = requests.get(URL, headers=HEADERS, timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")
print(f"HTTP: {resp.status_code}")

h1 = soup.find("h1")
print(f"\nH1: {h1.get_text(strip=True) if h1 else 'НЕТ'}")

for prop in ["calories","proteinContent","fatContent","carbohydrateContent","recipeYield","totalTime"]:
    el = soup.select_one(f"[itemprop='{prop}']")
    if el:
        print(f"  {prop}: content={el.get('content')} | text={el.get_text(strip=True)[:50]}")

for sel in ["[itemprop='recipeIngredient']","[itemprop='ingredients']",".ingredients li",".ingr li",".recipe_ing li"]:
    items = soup.select(sel)
    if items:
        print(f"\nИнгредиенты [{sel}] ({len(items)}):")
        for i in items[:5]: print(f"  {i.get_text(strip=True)[:80]}")
        break

for sel in ["[itemprop='recipeInstructions']",".instructions li",".recipe_step",".step",".cooking li"]:
    items = soup.select(sel)
    if items:
        print(f"\nШаги [{sel}] ({len(items)}):")
        for i in items[:3]: print(f"  {i.get_text(strip=True)[:100]}")
        break

for sel in ["img[itemprop='image']",".recipe_photo img",".foto img","img.foto"]:
    img = soup.select_one(sel)
    if img:
        print(f"\nФото [{sel}]: src={img.get('src') or img.get('data-src')}")
        break
