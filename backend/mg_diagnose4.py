import requests
from bs4 import BeautifulSoup
import re

URL = "https://www.russianfood.com/recipes/recipe.php?rid=165737"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

resp = requests.get(URL, headers=HEADERS, timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")

# все itemprop на странице
print("=== ВСЕ itemprop ===")
for el in soup.find_all(itemprop=True):
    tag = el.name
    prop = el.get("itemprop")
    content = el.get("content") or el.get_text(strip=True)[:60]
    print(f"  <{tag}> {prop}: {content}")

# все классы div/ul/ol (топ-30 уникальных)
print("\n=== Классы блоков (div/ul/ol) ===")
classes = set()
for el in soup.find_all(["div","ul","ol","section"]):
    for c in (el.get("class") or []):
        classes.add(c)
for c in sorted(classes)[:40]:
    print(f"  .{c}")
