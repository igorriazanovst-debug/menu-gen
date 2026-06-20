import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
url = "https://www.russianfood.com/recipes/bytype/?fid=17&page=11"
soup = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=15).text, "html.parser")
links = [(a.get_text(strip=True), a['href']) for a in soup.find_all('a', href=True) if 'page=' in a.get('href','') and 'fid=17' in a.get('href','')]
for t, h in links: print(f"  [{t}] {h}")
