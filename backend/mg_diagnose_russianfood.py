import requests
from bs4 import BeautifulSoup
import re

URL = "https://www.russianfood.com/recipes/bytype/?fid=17"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

resp = requests.get(URL, headers=HEADERS, timeout=15)
print(f"HTTP: {resp.status_code}, len={len(resp.text)}")

soup = BeautifulSoup(resp.text, "html.parser")

links = [a['href'] for a in soup.find_all('a', href=True) if 'recipe' in a['href'].lower()]
print(f"\nСсылки с 'recipe' ({len(links)}):")
for l in links[:20]: print(f"  {l}")

patterns = set()
for h in [a.get('href','') for a in soup.find_all('a', href=True)]:
    m = re.match(r'(/[^/]*/[^/?]*)', h)
    if m: patterns.add(m.group(1))
print(f"\nПаттерны href ({len(patterns)}):")
for p in sorted(patterns)[:30]: print(f"  {p}")

body = soup.find('body')
if body:
    print("\nBody text (600 символов):")
    print(body.get_text(separator='\n', strip=True)[:600])
