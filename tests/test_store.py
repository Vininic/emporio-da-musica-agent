from emporio.store import Availability, phone_digits


def test_loads_every_table(store):
    assert len(store.all_products()) == 65
    assert len(store.categories()) == 9
    assert len(store.active_promotions()) == 4


def test_t05_categories_without_products_are_visible_as_empty(store):
    empty = {c["name"] for c in store.categories() if not c["available"]}
    assert empty == {
        "Instrumentos de Sopro (Madeiras)",
        "Instrumentos de Sopro (Metais)",
        "Cordas Orquestrais",
    }


def test_t07_only_sellable_guitars_under_a_thousand(store):
    guitars = store.filter_products(category_id=5, max_price_cents=100000)
    assert len(guitars) == 12
    names = {p.name for p in guitars}
    assert "Giannini GF-3D Dreadnought Sunburst" not in names
    assert "Shelby SN-7C 7 Cordas Nylon Natural" not in names


def test_t07_unavailable_ones_appear_only_when_asked(store):
    assert (
        len(store.filter_products(category_id=5, max_price_cents=100000, only_available=False))
        == 14
    )


def test_t08_status_beats_stock(store):
    bass = store.product(136)
    assert bass.stock == 13
    assert bass.availability is Availability.DISCONTINUED


def test_t09_coming_soon_is_not_for_sale(store):
    kala = store.product(130)
    assert kala.stock == 2
    assert kala.availability is Availability.COMING_SOON
    assert kala.id not in {p.id for p in store.filter_products()}


def test_t10_only_active_promotions_change_the_price(store):
    assert {p.id for p in store.active_promotions()} == {90, 94, 121, 127}
    assert store.product(121).quote().final_cents == 43920


def test_t11_expired_promotion_does_not_touch_the_price(store):
    takamine = store.product(95)
    assert takamine.promotion is None
    assert takamine.expired_promotions[0].percent == 12
    assert takamine.quote().final_cents == 219900


def test_t12_out_of_stock_with_two_expired_promotions(store):
    giannini = store.product(96)
    assert giannini.availability is Availability.OUT_OF_STOCK
    assert sorted(p.percent for p in giannini.expired_promotions) == [18, 40]


def test_filters_by_final_price_so_a_promotion_can_bring_a_product_into_range(store):
    assert 121 in {p.id for p in store.filter_products(max_price_cents=45000)}


def test_filters_by_strings_and_electronics(store):
    nylon = store.filter_products(category_id=5, strings="nylon", electric=False)
    assert nylon
    assert all(p.specs["strings"] == "nylon" and p.specs["electronics"] == "no" for p in nylon)


def test_t15_order_total_is_the_stored_one(store):
    phone = _phone_of_order(store, 3)
    assert store.verified_order(3, phone).total_cents == 345000


def test_t19_order_requires_matching_phone(store):
    assert store.verified_order(1, "(67) 98432-1098") is not None
    assert store.verified_order(1, "67984321098") is not None
    assert store.verified_order(1, "+55 67 98432-1098") is not None
    assert store.verified_order(1, "(67) 99812-3456") is None
    assert store.verified_order(999, "(67) 98432-1098") is None


def test_t19_order_exposes_only_the_first_name(store):
    order = store.verified_order(1, "(67) 98432-1098")
    assert order.customer_first_name == "Pedro"
    assert not hasattr(order, "email")


def test_t18_shared_email_does_not_merge_customers(store):
    assert store.verified_order(10, "(67) 98543-2109") is not None
    assert store.verified_order(10, "(67) 99456-3456") is None


def test_phone_digits():
    assert phone_digits("(67) 98432-1098") == "67984321098"
    assert phone_digits("5567984321098") == "67984321098"


def _phone_of_order(store, order_id):
    row = store._db.execute(
        """
        SELECT cu.phone_digits FROM orders o
        JOIN customers cu ON cu.id = o.customer_id WHERE o.id = ?
        """,
        (order_id,),
    ).fetchone()
    return row["phone_digits"]
