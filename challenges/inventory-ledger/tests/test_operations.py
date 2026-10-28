from datetime import date

import pytest
from inventory import (
    Item,
    Ledger,
    Location,
    LocationError,
    MovementKind,
    OrderStatus,
    PurchaseOrder,
    StockError,
    StockMap,
    Supplier,
    draft_order,
)
from inventory.movements import movements_between, movements_for, net_change, totals_by_kind
from inventory.reports import (
    activity,
    format_stock_table,
    iter_pages,
    stock_lines,
    valuation_summary,
)

DAY_1 = date(2026, 3, 1)
DAY_2 = date(2026, 3, 2)
DAY_3 = date(2026, 3, 3)


def build_ledger() -> Ledger:
    ledger = Ledger()
    ledger.add_item(Item("A-100", "Bolt", 0.25, quantity=400, reorder_level=100))
    ledger.add_item(Item("C-300", "Hinge", 7.0, quantity=2, reorder_level=10))
    ledger.add_item(Item("D-400", "Spacer", 1.2, quantity=3, reorder_level=0))
    return ledger


def build_history() -> Ledger:
    ledger = build_ledger()
    ledger.receive("A-100", 50, reference="PO-1", on=DAY_1)
    ledger.dispatch("A-100", 30, reference="SO-7", on=DAY_2)
    ledger.dispatch("C-300", 2, on=DAY_2)
    ledger.adjust("A-100", 410, reason="stocktake", on=DAY_3)
    return ledger


def test_item_stock_value():
    assert Item("X", "Washer", 0.5, quantity=8).stock_value == pytest.approx(4.0)


def test_item_lookup():
    ledger = build_ledger()
    assert ledger.item("C-300").name == "Hinge"
    with pytest.raises(StockError):
        ledger.item("Z-999")


def test_movements_are_recorded_in_order():
    history = build_history().history
    assert [(m.sku, m.kind, m.quantity) for m in history] == [
        ("A-100", MovementKind.RECEIPT, 50),
        ("A-100", MovementKind.DISPATCH, -30),
        ("C-300", MovementKind.DISPATCH, -2),
        ("A-100", MovementKind.ADJUSTMENT, -10),
    ]
    assert history[0].reference == "PO-1"
    assert history[0].is_inbound
    assert not history[1].is_inbound


def test_movement_date_defaults_to_today():
    ledger = build_ledger()
    ledger.receive("C-300", 1)
    assert ledger.history[0].on == date.today()


def test_rejected_movement_is_not_recorded():
    ledger = build_ledger()
    with pytest.raises(StockError):
        ledger.dispatch("C-300", 5)
    assert ledger.history == []


def test_adjust_sets_counted_quantity():
    ledger = build_ledger()
    assert ledger.adjust("C-300", 6, reason="found") == 4
    assert ledger.items["C-300"].quantity == 6


def test_adjust_without_difference_records_nothing():
    ledger = build_ledger()
    assert ledger.adjust("C-300", 2) == 0
    assert ledger.history == []


def test_adjust_rejects_negative_count():
    with pytest.raises(StockError):
        build_ledger().adjust("C-300", -1)


def test_page_count():
    ledger = build_ledger()
    assert ledger.page_count(2) == 2
    assert ledger.page_count(3) == 1
    assert Ledger().page_count() == 0
    with pytest.raises(ValueError):
        ledger.page_count(0)


def test_movement_queries():
    history = build_history().history
    assert len(movements_for(history, "A-100")) == 3
    assert net_change(history, "A-100") == 10
    assert net_change(history, "Z-999") == 0
    assert [m.sku for m in movements_between(history, DAY_2, DAY_2)] == ["A-100", "C-300"]
    with pytest.raises(ValueError):
        movements_between(history, DAY_3, DAY_1)


def test_totals_by_kind_includes_every_kind():
    assert totals_by_kind(build_history().history) == {
        MovementKind.RECEIPT: 50,
        MovementKind.DISPATCH: -32,
        MovementKind.ADJUSTMENT: -10,
    }
    assert totals_by_kind([]) == dict.fromkeys(MovementKind, 0)


def test_location_parse_and_format():
    location = Location.parse(" b-03-2 ")
    assert location == Location("B", 3, 2)
    assert str(location) == "B-03-2"
    for code in ("B-03", "-03-2", "B-x-2", "B-03-2-1"):
        with pytest.raises(LocationError):
            Location.parse(code)


def test_locations_order_by_walking_route():
    codes = ["B-01-1", "A-10-1", "A-02-3", "A-02-1"]
    assert [str(loc) for loc in sorted(map(Location.parse, codes))] == [
        "A-02-1",
        "A-02-3",
        "A-10-1",
        "B-01-1",
    ]


def test_stock_map_put_take_and_move():
    shelf, overflow = Location("A", 1, 1), Location("B", 2, 1)
    stock = StockMap()
    stock.put(shelf, "C-300", 5)
    stock.put(shelf, "C-300", 3)
    stock.move(shelf, overflow, "C-300", 6)
    assert stock.quantity_at(shelf, "C-300") == 2
    assert stock.quantity_at(overflow, "C-300") == 6
    assert stock.locations_of("C-300") == [shelf, overflow]
    assert stock.total_for("C-300") == 8
    stock.take(shelf, "C-300", 2)
    assert stock.locations_of("C-300") == [overflow]
    assert shelf not in stock.placements


def test_stock_map_rejects_invalid_quantities():
    shelf, other = Location("A", 1, 1), Location("A", 1, 2)
    stock = StockMap()
    stock.put(shelf, "C-300", 2)
    with pytest.raises(LocationError):
        stock.put(shelf, "C-300", 0)
    with pytest.raises(LocationError):
        stock.take(shelf, "C-300", 3)
    with pytest.raises(LocationError):
        stock.move(shelf, other, "C-300", 3)
    assert stock.quantity_at(shelf, "C-300") == 2
    assert stock.quantity_at(other, "C-300") == 0


def test_stock_map_discrepancies():
    stock = StockMap()
    stock.put(Location("A", 1, 1), "A-100", 390)
    stock.put(Location("A", 1, 2), "C-300", 2)
    stock.put(Location("A", 1, 2), "Q-1", 4)
    assert stock.discrepancies(build_ledger()) == {"A-100": 10, "D-400": 3, "Q-1": -4}


def test_purchase_order_lines_and_totals():
    order = PurchaseOrder("PO-9", Supplier("ACME", "Acme Ltd", lead_time_days=5), DAY_1)
    order.add_line("A-100", 200, 0.2)
    order.add_line("C-300", 8, 6.5)
    assert order.total_cost() == pytest.approx(92.0)
    assert order.expected_on == date(2026, 3, 6)
    for args in (("A-100", 1, 1.0), ("E-1", 0, 1.0), ("E-1", 1, -1.0)):
        with pytest.raises(ValueError):
            order.add_line(*args)


def test_purchase_order_receipts_update_ledger_and_status():
    ledger = build_ledger()
    order = PurchaseOrder("PO-9", Supplier("ACME", "Acme Ltd"), DAY_1)
    order.add_line("A-100", 200, 0.2)
    order.add_line("C-300", 8, 6.5)
    assert order.status is OrderStatus.OPEN
    order.receive(ledger, "C-300", 8, on=DAY_2)
    assert order.status is OrderStatus.PARTIAL
    assert order.outstanding("C-300") == 0
    order.receive(ledger, "A-100", 200, on=DAY_3)
    assert order.status is OrderStatus.RECEIVED
    assert ledger.items["C-300"].quantity == 10
    assert ledger.history[0].reference == "PO-9"


def test_purchase_order_rejects_over_delivery():
    ledger = build_ledger()
    order = PurchaseOrder("PO-9", Supplier("ACME", "Acme Ltd"), DAY_1)
    order.add_line("C-300", 8, 6.5)
    with pytest.raises(StockError):
        order.receive(ledger, "C-300", 9)
    with pytest.raises(StockError):
        order.receive(ledger, "A-100", 1)
    assert ledger.items["C-300"].quantity == 2
    assert order.received == {}


def test_draft_order_tops_up_low_items():
    ledger = build_ledger()
    order = draft_order(ledger, Supplier("ACME", "Acme Ltd"), "PO-10", DAY_1)
    assert [(line.sku, line.quantity, line.unit_cost) for line in order.lines] == [
        ("C-300", 18, 7.0)
    ]
    assert order.status is OrderStatus.OPEN


def test_stock_lines_and_summary():
    ledger = build_ledger()
    lines = stock_lines(ledger)
    assert [(line.sku, line.value, line.reorder) for line in lines] == [
        ("A-100", 100.0, False),
        ("C-300", 14.0, True),
        ("D-400", 3.6, False),
    ]
    summary = valuation_summary(ledger)
    assert (summary.item_count, summary.unit_count, summary.reorder_count) == (3, 405, 1)


def test_format_stock_table_rows():
    rows = format_stock_table(build_ledger()).splitlines()
    assert rows[0].split() == ["SKU", "Name", "Qty", "Value"]
    assert rows[2].split() == ["C-300", "Hinge", "2", "14.00", "*"]
    assert rows[1].split() == ["A-100", "Bolt", "400", "100.00"]
    assert rows[-1].startswith("Total")
    assert len(rows) == 5


def test_iter_pages_on_empty_ledger_and_invalid_size():
    assert list(iter_pages(Ledger())) == []
    with pytest.raises(ValueError):
        list(iter_pages(build_ledger(), size=0))


def test_activity_nets_movements_in_period():
    ledger = build_history()
    assert activity(ledger, DAY_2, DAY_3) == {"A-100": -40, "C-300": -2}
    assert activity(ledger, date(2026, 4, 1), date(2026, 4, 30)) == {}
