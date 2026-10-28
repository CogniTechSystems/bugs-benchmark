import pytest
from inventory import Item, Ledger, StockError


def build_ledger() -> Ledger:
    ledger = Ledger()
    ledger.add_item(Item("A-100", "Bolt", 0.25, quantity=400, reorder_level=100))
    ledger.add_item(Item("B-200", "Bracket", 3.5, quantity=5, reorder_level=5))
    ledger.add_item(Item("C-300", "Hinge", 7.0, quantity=2, reorder_level=10))
    return ledger


def test_receive_increases_quantity():
    ledger = build_ledger()
    ledger.receive("A-100", 50)
    assert ledger.items["A-100"].quantity == 450


def test_receive_rejects_non_positive_quantity():
    with pytest.raises(StockError):
        build_ledger().receive("A-100", 0)


def test_dispatch_reduces_quantity():
    ledger = build_ledger()
    ledger.dispatch("A-100", 150)
    assert ledger.items["A-100"].quantity == 250


def test_dispatch_can_empty_stock():
    ledger = build_ledger()
    ledger.dispatch("B-200", 5)
    assert ledger.items["B-200"].quantity == 0


def test_dispatch_rejects_more_than_in_stock():
    ledger = build_ledger()
    with pytest.raises(StockError):
        ledger.dispatch("C-300", 3)
    assert ledger.items["C-300"].quantity == 2


def test_unknown_sku_raises():
    with pytest.raises(StockError):
        build_ledger().receive("Z-999", 1)


def test_duplicate_sku_is_rejected():
    ledger = build_ledger()
    with pytest.raises(StockError):
        ledger.add_item(Item("A-100", "Duplicate", 1.0))


def test_total_value_multiplies_price_by_quantity():
    assert build_ledger().total_value() == pytest.approx(131.5)


def test_total_value_of_empty_ledger_is_zero():
    assert Ledger().total_value() == 0


def test_items_to_reorder_includes_items_at_reorder_level():
    assert build_ledger().items_to_reorder() == ["B-200", "C-300"]


def test_first_page_starts_with_first_item():
    page = build_ledger().page(1, size=2)
    assert [item.sku for item in page] == ["A-100", "B-200"]


def test_last_page_contains_remaining_items():
    page = build_ledger().page(2, size=2)
    assert [item.sku for item in page] == ["C-300"]


def test_page_number_must_be_positive():
    with pytest.raises(ValueError):
        build_ledger().page(0)
