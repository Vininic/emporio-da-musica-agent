import html
import json
import re
import time
import urllib.parse
import urllib.request

from emporio.config import ROOT
from emporio.store import Store, normalize_text

OUTPUT = ROOT / "data" / "product_images.json"
SEARCH = "https://www.bing.com/images/async?q={query}&first=0&count=12&adlt=strict"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
PAUSE = 2.0
THROTTLE_PAUSE = 10.0
ATTEMPTS = 3
FINISH_WORDS = {"natural", "sunburst", "preto", "branco", "nylon", "aco", "folk", "dreadnought"}
REJECTED_ON_REVIEW = {91, 139, 140, 141, 142, 143, 144}


def _get(url: str) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", "replace")


def required_words(name: str) -> list[str]:
    words = normalize_text(name).split()
    brand, *rest = words
    model = [word for word in rest if any(char.isdigit() for char in word)]
    if not model:
        model = [word for word in rest if word not in FINISH_WORDS][:1]
    return [brand, *model]


def matches(name: str, title: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", normalize_text(title))
    return all(re.sub(r"[^a-z0-9]", "", word) in compact for word in required_words(name))


def find_image(name: str) -> dict | None:
    for attempt in range(ATTEMPTS):
        page = _get(SEARCH.format(query=urllib.parse.quote(name)))
        results = re.findall(r'class="iusc"[^>]*\bm="([^"]+)"', page)
        if results:
            break
        time.sleep(THROTTLE_PAUSE * (attempt + 1))
    for raw in results:
        result = json.loads(html.unescape(raw))
        if result.get("turl") and matches(name, result.get("t", "")):
            return {"url": result["turl"], "source": result.get("purl", ""), "title": result["t"]}
    return None


def main() -> None:
    images = json.loads(OUTPUT.read_text("utf-8")) if OUTPUT.exists() else {}
    products = Store(ROOT / "data" / "raw").all_products()
    for product in products:
        if str(product.id) in images or product.id in REJECTED_ON_REVIEW:
            continue
        image = find_image(product.name)
        if image:
            images[str(product.id)] = image
            OUTPUT.write_text(json.dumps(images, ensure_ascii=False, indent=1), encoding="utf-8")
        print("ok  " if image else "miss", product.id, product.name, flush=True)
        time.sleep(PAUSE)
    print(f"{len(images)}/{len(products)} products have an image")


if __name__ == "__main__":
    main()
