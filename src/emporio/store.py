import csv
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from emporio.domain.money import to_cents
from emporio.domain.pricing import Promotion, Quote, quote

SCHEMA = """
CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT, description TEXT);
CREATE TABLE products (
    id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER, description TEXT,
    price_cents INTEGER, stock INTEGER, status TEXT, specs TEXT
);
CREATE TABLE promotions (
    id INTEGER PRIMARY KEY, product_id INTEGER, percent INTEGER, name TEXT, active INTEGER
);
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, phone_digits TEXT, city TEXT);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT, status TEXT,
    total_cents INTEGER, payment_method TEXT, tracking_code TEXT,
    estimated_delivery TEXT, notes TEXT
);
CREATE TABLE order_items (order_id INTEGER, product_id INTEGER, quantity INTEGER);
"""


class Availability(StrEnum):
    AVAILABLE = "disponivel"
    OUT_OF_STOCK = "esgotado"
    DISCONTINUED = "descontinuado"
    COMING_SOON = "em_breve"


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category_id: int
    category: str
    description: str
    price_cents: int
    stock: int
    status: str
    specs: dict
    promotion: Promotion | None
    expired_promotions: tuple[Promotion, ...]

    @property
    def availability(self) -> Availability:
        if self.status == "discontinued":
            return Availability.DISCONTINUED
        if self.status == "coming_soon":
            return Availability.COMING_SOON
        return Availability.AVAILABLE if self.stock > 0 else Availability.OUT_OF_STOCK

    def quote(self, quantity: int = 1) -> Quote:
        return quote(self.price_cents, self.promotion, quantity)


@dataclass(frozen=True)
class OrderItem:
    product_name: str
    quantity: int


@dataclass(frozen=True)
class Order:
    id: int
    customer_first_name: str
    order_date: str
    status: str
    total_cents: int
    payment_method: str
    tracking_code: str | None
    estimated_delivery: str | None
    notes: str | None
    items: tuple[OrderItem, ...]


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def phone_digits(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return digits[2:] if digits.startswith("55") and len(digits) > 11 else digits


def _rows(raw_dir: Path, name: str) -> list[dict]:
    with open(raw_dir / f"{name}.csv", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


class Store:
    def __init__(self, raw_dir: Path):
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._load(raw_dir)

    def _load(self, raw_dir: Path) -> None:
        self._db.executemany(
            "INSERT INTO categories VALUES (?, ?, ?)",
            [(r["category_id"], r["name"], r["description"]) for r in _rows(raw_dir, "categories")],
        )
        self._db.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["product_id"],
                    r["name"],
                    r["category_id"],
                    r["description"],
                    to_cents(r["price_brl"]),
                    r["stock_quantity"],
                    r["status"],
                    r["specs"],
                )
                for r in _rows(raw_dir, "products")
            ],
        )
        self._db.executemany(
            "INSERT INTO promotions VALUES (?, ?, ?, ?, ?)",
            [
                (
                    r["promotion_id"],
                    r["product_id"],
                    r["discount_percent"],
                    r["description"],
                    r["is_active"],
                )
                for r in _rows(raw_dir, "promotions")
            ],
        )
        self._db.executemany(
            "INSERT INTO customers VALUES (?, ?, ?, ?)",
            [
                (r["customer_id"], r["name"], phone_digits(r["phone"]), r["city"])
                for r in _rows(raw_dir, "customers")
            ],
        )
        self._db.executemany(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["order_id"],
                    r["customer_id"],
                    r["order_date"],
                    r["status"],
                    to_cents(r["total_brl"]),
                    r["payment_method"],
                    r["tracking_code"] or None,
                    r["estimated_delivery"] or None,
                    r["notes"] or None,
                )
                for r in _rows(raw_dir, "orders")
            ],
        )
        self._db.executemany(
            "INSERT INTO order_items VALUES (?, ?, ?)",
            [
                (r["order_id"], r["product_id"], r["quantity"])
                for r in _rows(raw_dir, "order_items")
            ],
        )

    def categories(self) -> list[dict]:
        rows = self._db.execute(
            """
            SELECT c.id, c.name, c.description,
                   SUM(CASE WHEN p.status = 'active' AND p.stock > 0 THEN 1 ELSE 0 END) AS available
            FROM categories c LEFT JOIN products p ON p.category_id = c.id
            GROUP BY c.id ORDER BY c.id
            """
        )
        return [dict(row) for row in rows]

    def _build_products(self, rows: list[sqlite3.Row]) -> list[Product]:
        if not rows:
            return []
        promotions = self._db.execute("SELECT product_id, percent, name, active FROM promotions")
        active: dict[int, Promotion] = {}
        expired: dict[int, list[Promotion]] = {}
        for row in promotions:
            promotion = Promotion(row["percent"], row["name"])
            if not row["active"]:
                expired.setdefault(row["product_id"], []).append(promotion)
            elif (
                row["product_id"] not in active
                or promotion.percent > active[row["product_id"]].percent
            ):
                active[row["product_id"]] = promotion

        return [
            Product(
                id=row["id"],
                name=row["name"],
                category_id=row["category_id"],
                category=row["category"],
                description=row["description"],
                price_cents=row["price_cents"],
                stock=row["stock"],
                status=row["status"],
                specs=json.loads(row["specs"]),
                promotion=active.get(row["id"]),
                expired_promotions=tuple(expired.get(row["id"], ())),
            )
            for row in rows
        ]

    _PRODUCT_SELECT = """
        SELECT p.*, c.name AS category FROM products p
        JOIN categories c ON c.id = p.category_id
    """

    def all_products(self) -> list[Product]:
        rows = self._db.execute(self._PRODUCT_SELECT + " ORDER BY p.id").fetchall()
        return self._build_products(rows)

    def product(self, product_id: int) -> Product | None:
        rows = self._db.execute(self._PRODUCT_SELECT + " WHERE p.id = ?", (product_id,)).fetchall()
        products = self._build_products(rows)
        return products[0] if products else None

    def filter_products(
        self,
        category_id: int | None = None,
        max_price_cents: int | None = None,
        min_price_cents: int | None = None,
        strings: str | None = None,
        electric: bool | None = None,
        only_available: bool = True,
    ) -> list[Product]:
        clauses, params = [], []
        if category_id is not None:
            clauses.append("p.category_id = ?")
            params.append(category_id)
        if min_price_cents is not None:
            clauses.append("p.price_cents >= ?")
            params.append(min_price_cents)
        if only_available:
            clauses.append("p.status = 'active' AND p.stock > 0")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._db.execute(f"{self._PRODUCT_SELECT}{where} ORDER BY p.price_cents", params)
        products = self._build_products(rows.fetchall())

        if max_price_cents is not None:
            products = [p for p in products if p.quote().final_cents <= max_price_cents]
        if strings is not None:
            products = [
                p
                for p in products
                if normalize_text(strings) in normalize_text(str(p.specs.get("strings", "")))
            ]
        if electric is not None:
            products = [
                p for p in products if (p.specs.get("electronics") not in (None, "no")) == electric
            ]
        return products

    def active_promotions(self) -> list[Product]:
        rows = self._db.execute(
            self._PRODUCT_SELECT
            + " JOIN promotions pr ON pr.product_id = p.id WHERE pr.active = 1 ORDER BY p.id"
        ).fetchall()
        return self._build_products(rows)

    def verified_order(self, order_id: int, phone: str) -> Order | None:
        match = self._db.execute(
            """
            SELECT 1 FROM orders o JOIN customers cu ON cu.id = o.customer_id
            WHERE o.id = ? AND cu.phone_digits = ?
            """,
            (order_id, phone_digits(phone)),
        ).fetchone()
        return self.order_for_verified_session(order_id) if match else None

    def order_for_verified_session(self, order_id: int) -> Order | None:
        row = self._db.execute(
            """
            SELECT o.*, cu.name AS customer_name FROM orders o
            JOIN customers cu ON cu.id = o.customer_id WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
        if row is None:
            return None

        items = self._db.execute(
            """
            SELECT p.name, oi.quantity FROM order_items oi
            JOIN products p ON p.id = oi.product_id WHERE oi.order_id = ?
            """,
            (order_id,),
        ).fetchall()
        return Order(
            id=row["id"],
            customer_first_name=row["customer_name"].split()[0],
            order_date=row["order_date"],
            status=row["status"],
            total_cents=row["total_cents"],
            payment_method=row["payment_method"],
            tracking_code=row["tracking_code"],
            estimated_delivery=row["estimated_delivery"],
            notes=row["notes"],
            items=tuple(OrderItem(i["name"], i["quantity"]) for i in items),
        )
