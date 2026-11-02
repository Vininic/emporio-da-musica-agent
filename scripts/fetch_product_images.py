import html
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image

from emporio.config import ROOT
from emporio.store import Product, Store, normalize_text

OUTPUT = ROOT / "data" / "product_images.json"
SEARCH = "https://www.bing.com/images/async?q={query}&first=0&count=20&adlt=strict"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
PAUSE = 2.0
THROTTLE_PAUSE = 10.0
ATTEMPTS = 3
CANDIDATES = 6
THUMBNAIL_SIZE = "&w=480&h=480"
TYPE_WORDS = {"teclado", "sintetizador", "bateria", "acustica", "eletrica", "eletronica"}
FINISH_WORDS = {"natural", "sunburst", "preto", "branco", "nylon", "aco", "folk", "dreadnought"}
CATEGORY_QUERIES = {
    1: "electric guitar",
    2: "electric bass guitar",
    3: "acoustic drum kit",
    4: "synthesizer music workstation",
    5: "violão",
    9: "ukulele",
}
REJECTED_EXACT = {91, 139, 140, 141, 142, 143, 144}
REVIEWED_QUERIES = {
    83: ("Tagima Memphis AC-39 violão inteiro", ["tagima", "39"], True),
    85: ("violão clássico nylon natural estudante", ["violao"], True),
    109: ("violão 7 cordas nylon natural", ["7"], True),
    111: ("violão 7 cordas eletroacústico nylon natural", ["7"], True),
    126: ("Kala KA-SRT-CTG tenor ukulele front", ["kala", "srt"], False),
    133: ("PRS SE Custom 24 electric guitar full body", ["prs", "24"], False),
    137: ("Yamaha TRBX electric bass guitar", ["yamaha"], True),
}
WHITE = 238


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()


def brand_of(name: str) -> str:
    return next(word for word in normalize_text(name).split() if word not in TYPE_WORDS)


def required_words(name: str) -> list[str]:
    words = [word for word in normalize_text(name).split() if word not in TYPE_WORDS]
    brand, *rest = words
    model = [word for word in rest if any(char.isdigit() for char in word) and len(word) > 1]
    if not model:
        model = [word for word in rest if word not in FINISH_WORDS][:1]
    return [brand, *model]


def matches(words: list[str], result: dict) -> bool:
    title = re.sub(
        r"[^a-z0-9]", "", normalize_text(f"{result.get('t', '')} {result.get('purl', '')}")
    )
    return all(re.sub(r"[^a-z0-9]", "", word) in title for word in words)


def studio_score(data: bytes) -> float:
    picture = Image.open(io.BytesIO(data)).convert("L")
    picture.thumbnail((120, 120))
    width, height = picture.size
    pixels = picture.load()
    frame = [
        pixels[x, y]
        for x in range(width)
        for y in range(height)
        if x < 4 or y < 4 or x >= width - 4 or y >= height - 4
    ]
    whiteness = sum(value >= WHITE for value in frame) / len(frame)
    mask = picture.point(lambda value: 255 if value < WHITE else 0)
    box = mask.getbbox() or (0, 0, width, height)
    touching = sum((box[0] <= 1, box[1] <= 1, box[2] >= width - 1, box[3] >= height - 1))
    filled = (box[3] - box[1]) / height
    return whiteness * 2 - touching * 0.6 + filled * 0.5


def search(query: str) -> list[dict]:
    for attempt in range(ATTEMPTS):
        page = _get(SEARCH.format(query=urllib.parse.quote(query))).decode("utf-8", "replace")
        results = re.findall(r'class="iusc"[^>]*\bm="([^"]+)"', page)
        if results:
            return [json.loads(html.unescape(raw)) for raw in results]
        time.sleep(THROTTLE_PAUSE * (attempt + 1))
    return []


def best_image(
    results: list[dict], words: list[str], illustrative: bool, skip: frozenset[str] = frozenset()
) -> dict | None:
    scored = []
    usable = [r for r in results if r.get("turl") and r["turl"] not in skip and matches(words, r)]
    for result in usable[:CANDIDATES]:
        url = result["turl"] + THUMBNAIL_SIZE
        try:
            scored.append((studio_score(_get(url)), url, result))
        except Exception:
            continue
    if not scored:
        return None
    _, url, result = max(scored, key=lambda item: item[0])
    return {
        "url": url,
        "source": result.get("purl", ""),
        "title": result.get("t", ""),
        "illustrative": illustrative,
    }


def find_image(product: Product, skip: frozenset[str] = frozenset()) -> dict | None:
    if product.id in REVIEWED_QUERIES:
        query, words, illustrative = REVIEWED_QUERIES[product.id]
        return best_image(search(query), words, illustrative, skip)
    if product.id not in REJECTED_EXACT:
        found = best_image(search(product.name), required_words(product.name), False)
        if found:
            return found
        time.sleep(PAUSE)
    brand = brand_of(product.name)
    kind = CATEGORY_QUERIES.get(product.category_id, "instrument")
    strings = "nylon" if "nylon" in normalize_text(product.name) else ""
    return best_image(search(f"{brand} {kind} {strings}".strip()), [brand], True)


def main() -> None:
    only = {int(value) for value in sys.argv[1:]}
    images = json.loads(OUTPUT.read_text("utf-8")) if only and OUTPUT.exists() else {}
    products = Store(ROOT / "data" / "raw").all_products()
    for product in products:
        if only and product.id not in only:
            continue
        current = images.get(str(product.id), {}).get("url", "").removesuffix(THUMBNAIL_SIZE)
        image = find_image(product, frozenset({current}))
        if image:
            images[str(product.id)] = image
            OUTPUT.write_text(json.dumps(images, ensure_ascii=False, indent=1), encoding="utf-8")
        label = "miss" if not image else "illus" if image["illustrative"] else "exact"
        print(label, product.id, product.name, flush=True)
        time.sleep(PAUSE)
    exact = sum(not image["illustrative"] for image in images.values())
    print(f"{exact} exact and {len(images) - exact} illustrative of {len(products)} products")


if __name__ == "__main__":
    main()
