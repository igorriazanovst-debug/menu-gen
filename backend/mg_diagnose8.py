import requests, re
from bs4 import BeautifulSoup

URL = "https://www.russianfood.com/recipes/recipe.php?rid=165737"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

resp = requests.get(URL, headers=HEADERS, timeout=15)
html = resp.text
soup = BeautifulSoup(html, "html.parser")

# meta теги
print("=== META TAGS ===")
for m in soup.find_all("meta"):
    name = m.get("name") or m.get("property") or ""
    content = (m.get("content") or "")[:200]
    if content:
        print(f"  {name}: {content}")

# HTML вокруг шагов (pos 152504)
print("\n=== HTML вокруг pos 152504 (шаги) ===")
chunk = html[152000:154000]
print(re.sub(r'<[^>]+>', ' ', chunk)[:800])

# ищем блок с шагами по паттерну step
print("\n=== div/td с шагами ===")
for el in soup.find_all(["div","td","li"], class_=re.compile(r'step|howcook|cook_step|instruction', re.I)):
    print(f"  [{el.get('class')}]: {el.get_text(strip=True)[:100]}")
