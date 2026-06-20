import requests
from bs4 import BeautifulSoup

URL = "https://www.russianfood.com/recipes/bytype/?fid=17"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

resp = requests.get(URL, headers=HEADERS, timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")

# полные ссылки на recipe.php
links = [a['href'] for a in soup.find_all('a', href=True) if 'recipe.php' in a['href']]
print(f"Ссылки recipe.php ({len(links)}):")
for l in links[:30]: print(f"  {l}")

# пагинация
print("\nСсылки с 'page' или 'fid=17':")
for a in soup.find_all('a', href=True):
    h = a['href']
    if 'fid=17' in h or ('page' in h and 'fid' in h):
        print(f"  [{a.get_text(strip=True)[:20]}] {h}")

# один пример карточки рецепта
print("\nПервая карточка рецепта (родительский элемент первой recipe.php-ссылки):")
first = next((a for a in soup.find_all('a', href=True) if 'recipe.php' in a['href']), None)
if first:
    parent = first.find_parent(['div','li','article'])
    if parent:
        print(parent.prettify()[:800])
