import requests
from bs4 import BeautifulSoup

URL = "https://www.russianfood.com/recipes/recipe.php?rid=165737"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

resp = requests.get(URL, headers=HEADERS, timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")

for cls in ["howcook", "informb_r", "content", "desc_bcf", "img_c", "buttons"]:
    el = soup.select_one(f".{cls}")
    if el:
        print(f"\n=== .{cls} ===")
        print(el.prettify()[:600])
