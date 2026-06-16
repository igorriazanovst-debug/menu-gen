#!/usr/bin/env python3
"""Диагностика: смотрим HTML листинга russianfood.com и находим структуру ссылок."""
import sys
sys.path.insert(0, '/app')

import requests
from bs4 import BeautifulSoup

URL = "https://www.russianfood.com/recipes/bytype/?fid=17"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

resp = requests.get(URL, headers=HEADERS, timeout=15)
print(f"HTTP status: {resp.status_code}", flush=True)
print(f"Content-Type: {resp.headers.get('Content-Type')}", flush=True)
print(f"Content length: {len(resp.text)}", flush=True)
print("", flush=True)

soup = BeautifulSoup(resp.text, "html.parser")

# все <a> с href содержащим 'recipe'
recipe_links = [a['href'] for a in soup.find_all('a', href=True) if 'recipe' in a['href'].lower()]
print(f"Ссылки с 'recipe' в href ({len(recipe_links)}):")
for l in recipe_links[:20]:
    print(f"  {l}", flush=True)

print("", flush=True)

# все уникальные паттерны href
import re
all_hrefs = [a.get('href','') for a in soup.find_all('a', href=True)]
patterns = set()
for h in all_hrefs:
    # берём первые 2 сегмента пути
    m = re.match(r'(/[^/]*/[^/?]*)', h)
    if m:
        patterns.add(m.group(1))
print(f"Паттерны путей ({len(patterns)}):")
for p in sorted(patterns)[:30]:
    print(f"  {p}", flush=True)

print("", flush=True)

# первые 500 символов body
body = soup.find('body')
if body:
    text = body.get_text(separator='\n', strip=True)
    print("Первые 800 символов body text:")
    print(text[:800], flush=True)
