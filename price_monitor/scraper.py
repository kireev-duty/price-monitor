import logging
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from price_monitor.config import Settings, Source

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Item:
    source: str
    url: str
    title: str
    price: float | None
    in_stock: bool | None


_NUM_RE = re.compile(r"\d[\d\s .,']*")


def parse_price(text: str) -> float | None:
    """Достаёт число из строки цены: «£47.82», «1 299 ₽», «1.299,00 €», «от 2 490 руб.»."""
    m = _NUM_RE.search(text or "")
    if not m:
        return None
    num = re.sub(r"[\s ']", "", m.group()).rstrip(".,")
    if "," in num and "." in num:
        # Десятичный разделитель — тот, что стоит последним
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif "," in num:
        head, _, tail = num.rpartition(",")
        # «1,299» — разделитель тысяч, «12,50» — копейки
        num = num.replace(",", "") if len(tail) == 3 else f"{head.replace(',', '')}.{tail}"
    elif num.count(".") > 1:
        num = num.replace(".", "")
    try:
        return float(num)
    except ValueError:
        return None


def parse_listing(html: str, page_url: str, source: Source) -> tuple[list[Item], str | None]:
    """Разбирает страницу каталога: товары и ссылка на следующую страницу."""
    soup = BeautifulSoup(html, "html.parser")
    sel = source.selectors
    items = []
    for card in soup.select(sel.item):
        title_el = card.select_one(sel.title)
        link_el = card.select_one(sel.link)
        price_el = card.select_one(sel.price)
        if not (title_el and link_el):
            log.debug("Пропущена карточка без названия или ссылки на %s", page_url)
            continue
        title = (title_el.get(sel.title_attr) if sel.title_attr else None) or title_el.get_text(strip=True)
        in_stock = None
        if sel.availability:
            avail_el = card.select_one(sel.availability)
            if avail_el is not None:
                text = avail_el.get_text(" ", strip=True).lower()
                if any(w in text for w in source.out_of_stock_words):
                    in_stock = False
                else:
                    in_stock = any(w in text for w in source.in_stock_words)
        items.append(
            Item(
                source=source.name,
                url=urljoin(page_url, link_el.get("href", "")),
                title=title,
                price=parse_price(price_el.get_text(strip=True)) if price_el else None,
                in_stock=in_stock,
            )
        )
    next_url = None
    if sel.next_page:
        next_el = soup.select_one(sel.next_page)
        if next_el and next_el.get("href"):
            next_url = urljoin(page_url, next_el["href"])
    return items, next_url


def fetch(client: httpx.Client, url: str, retries: int = 3) -> str:
    for attempt in range(1, retries + 1):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as e:
            if attempt == retries:
                raise
            wait = 2**attempt
            log.warning("%s: %s — повтор через %s с", url, e, wait)
            time.sleep(wait)
    raise AssertionError("unreachable")


def make_client(settings: Settings) -> httpx.Client:
    return httpx.Client(headers={"User-Agent": settings.user_agent}, timeout=settings.timeout, follow_redirects=True)


def crawl(source: Source, settings: Settings, client: httpx.Client) -> Iterator[Item]:
    """Обходит каталог источника постранично, не больше source.max_pages страниц."""
    url, page = source.url, 0
    while url and page < source.max_pages:
        page += 1
        log.info("[%s] страница %s: %s", source.name, page, url)
        items, url = parse_listing(fetch(client, url), url, source)
        yield from items
        if url:
            time.sleep(settings.delay)
