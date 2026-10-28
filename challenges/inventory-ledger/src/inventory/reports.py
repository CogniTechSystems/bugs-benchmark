"""Read-only reports over a ledger for stock reviews and printed listings."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from inventory.ledger import Item, Ledger
from inventory.movements import movements_between


@dataclass(frozen=True)
class StockLine:
    """One row of a stock report giving an item's SKU, name, quantity, unit price, value and reorder
    flag.
    """

    sku: str
    name: str
    quantity: int
    unit_price: float
    value: float
    reorder: bool


@dataclass(frozen=True)
class ValuationSummary:
    """Headline figures for a ledger covering item count, units on hand, total stock value and items
    due for reordering.
    """

    item_count: int
    unit_count: int
    total_value: float
    reorder_count: int


def stock_lines(ledger: Ledger) -> list[StockLine]:
    """Return a report row for every item ordered by SKU, with its stock value rounded to two
    decimal places and its reorder flag.
    """
    due = set(ledger.items_to_reorder())
    return [
        StockLine(
            item.sku,
            item.name,
            item.quantity,
            item.unit_price,
            round(item.stock_value, 2),
            item.sku in due,
        )
        for item in sorted(ledger.items.values(), key=lambda item: item.sku)
    ]


def valuation_summary(ledger: Ledger) -> ValuationSummary:
    """Return the item count, units on hand, total stock value and count of items due for reordering
    in a ledger.
    """
    return ValuationSummary(
        item_count=len(ledger.items),
        unit_count=sum(item.quantity for item in ledger.items.values()),
        total_value=ledger.total_value(),
        reorder_count=len(ledger.items_to_reorder()),
    )


def iter_pages(ledger: Ledger, size: int = 10) -> Iterator[list[Item]]:
    """Yield successive item pages of the given size from the first onward, yielding nothing for an
    empty ledger.
    """
    for number in range(1, ledger.page_count(size) + 1):
        yield ledger.page(number, size)


def format_stock_table(ledger: Ledger) -> str:
    """Render a fixed-width text table with a header, one row per item ordered by SKU, starred
    reorder items and a total row.
    """
    rows = [f"{'SKU':<10}{'Name':<20}{'Qty':>8}{'Value':>12}"]
    for line in stock_lines(ledger):
        marker = " *" if line.reorder else ""
        rows.append(f"{line.sku:<10}{line.name:<20}{line.quantity:>8}{line.value:>12.2f}{marker}")
    summary = valuation_summary(ledger)
    rows.append(f"{'Total':<38}{summary.total_value:>12.2f}")
    return "\n".join(rows)


def activity(ledger: Ledger, start: date, end: date) -> dict[str, int]:
    """Return the net stock change per SKU, ordered by SKU, for movements dated start to end
    inclusive, keeping SKUs netting to zero.
    """
    totals: dict[str, int] = {}
    for movement in movements_between(ledger.history, start, end):
        totals[movement.sku] = totals.get(movement.sku, 0) + movement.quantity
    return dict(sorted(totals.items()))
