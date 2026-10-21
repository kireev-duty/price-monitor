import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Selectors:
    """CSS-селекторы карточки товара на странице каталога."""

    item: str
    title: str
    price: str
    link: str
    availability: str | None = None
    next_page: str | None = None
    # Атрибут, из которого брать название (например, title у ссылки); иначе — текст элемента
    title_attr: str | None = None


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    selectors: Selectors
    max_pages: int = 5
    # Слова, по которым товар считается «в наличии» (без учёта регистра)
    in_stock_words: tuple[str, ...] = ("in stock", "в наличии", "есть")
    # Проверяются первыми: «нет в наличии» содержит «в наличии»
    out_of_stock_words: tuple[str, ...] = ("out of stock", "нет в наличии", "нет на складе", "под заказ", "закончил")


@dataclass(frozen=True)
class Settings:
    db_path: str = "data/prices.db"
    delay: float = 1.0
    timeout: float = 20.0
    user_agent: str = "Mozilla/5.0 (compatible; price-monitor/0.1)"
    # Уведомлять, только если цена изменилась хотя бы на столько процентов
    notify_threshold: float = 0.0
    telegram_token: str | None = None
    telegram_chat_id: str | None = None


@dataclass(frozen=True)
class Config:
    settings: Settings
    sources: list[Source] = field(default_factory=list)


def load_config(path: str | Path) -> Config:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("settings", {})
    settings = Settings(
        db_path=raw.get("db_path", Settings.db_path),
        delay=float(raw.get("delay", Settings.delay)),
        timeout=float(raw.get("timeout", Settings.timeout)),
        user_agent=raw.get("user_agent", Settings.user_agent),
        notify_threshold=float(raw.get("notify_threshold", Settings.notify_threshold)),
        # Секреты — только из окружения, не из файла в репозитории
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
    )
    sources = [
        Source(
            name=s["name"],
            url=s["url"],
            max_pages=int(s.get("max_pages", 5)),
            in_stock_words=tuple(w.lower() for w in s.get("in_stock_words", Source.in_stock_words)),
            out_of_stock_words=tuple(w.lower() for w in s.get("out_of_stock_words", Source.out_of_stock_words)),
            selectors=Selectors(**s["selectors"]),
        )
        for s in data.get("source", [])
    ]
    if not sources:
        raise ValueError(f"В {path} нет ни одного [[source]]")
    return Config(settings=settings, sources=sources)
