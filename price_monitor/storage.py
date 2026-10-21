import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from price_monitor.scraper import Item

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id     INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    url    TEXT NOT NULL UNIQUE,
    title  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    product_id INTEGER NOT NULL REFERENCES products(id),
    price      REAL,
    in_stock   INTEGER,
    checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS prices_product ON prices(product_id, checked_at);
"""


@dataclass(frozen=True)
class Change:
    source: str
    title: str
    url: str
    old_price: float | None
    new_price: float | None
    old_in_stock: bool | None
    new_in_stock: bool | None
    is_new: bool = False

    @property
    def percent(self) -> float | None:
        if self.old_price and self.new_price is not None:
            return (self.new_price - self.old_price) / self.old_price * 100
        return None


def _to_bool(v: int | None) -> bool | None:
    return None if v is None else bool(v)


class Storage:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def save(self, items: list[Item], checked_at: datetime | None = None) -> list[Change]:
        """Сохраняет замер; возвращает новые товары и те, у которых изменилась цена или наличие."""
        ts = (checked_at or datetime.now()).isoformat(timespec="seconds")
        changes = []
        with self.conn:
            for it in items:
                row = self.conn.execute("SELECT id FROM products WHERE url = ?", (it.url,)).fetchone()
                last = None
                if row:
                    pid = row[0]
                    self.conn.execute("UPDATE products SET title = ? WHERE id = ?", (it.title, pid))
                    last = self.conn.execute(
                        "SELECT price, in_stock FROM prices WHERE product_id = ? ORDER BY checked_at DESC LIMIT 1",
                        (pid,),
                    ).fetchone()
                else:
                    pid = self.conn.execute(
                        "INSERT INTO products (source, url, title) VALUES (?, ?, ?)", (it.source, it.url, it.title)
                    ).lastrowid
                self.conn.execute(
                    "INSERT INTO prices (product_id, price, in_stock, checked_at) VALUES (?, ?, ?, ?)",
                    (pid, it.price, None if it.in_stock is None else int(it.in_stock), ts),
                )
                if last is None:
                    changes.append(Change(it.source, it.title, it.url, None, it.price, None, it.in_stock, is_new=True))
                elif last[0] != it.price or _to_bool(last[1]) != it.in_stock:
                    changes.append(
                        Change(it.source, it.title, it.url, last[0], it.price, _to_bool(last[1]), it.in_stock)
                    )
        return changes

    def current(self) -> list[dict]:
        """По каждому товару: последняя и предыдущая цена, минимум и максимум за всё время."""
        rows = self.conn.execute(
            """
            WITH ranked AS (
                SELECT product_id, price, in_stock, checked_at,
                       ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY checked_at DESC) AS rn
                FROM prices
            )
            SELECT p.source, p.title, p.url,
                   cur.price, prev.price, cur.in_stock, cur.checked_at,
                   (SELECT MIN(price) FROM prices WHERE product_id = p.id),
                   (SELECT MAX(price) FROM prices WHERE product_id = p.id)
            FROM products p
            JOIN ranked cur ON cur.product_id = p.id AND cur.rn = 1
            LEFT JOIN ranked prev ON prev.product_id = p.id AND prev.rn = 2
            ORDER BY p.source, p.title
            """
        ).fetchall()
        keys = ["source", "title", "url", "price", "prev_price", "in_stock", "checked_at", "min_price", "max_price"]
        return [dict(zip(keys, r)) for r in rows]

    def history(self) -> list[tuple]:
        return self.conn.execute(
            """
            SELECT p.source, p.title, p.url, pr.price, pr.in_stock, pr.checked_at
            FROM prices pr JOIN products p ON p.id = pr.product_id
            ORDER BY pr.checked_at, p.source, p.title
            """
        ).fetchall()
