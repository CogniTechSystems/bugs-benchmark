"""Stock tracking for a small warehouse."""

from dataclasses import dataclass, field
from datetime import date
from math import ceil

from inventory.movements import Movement, MovementKind


class StockError(Exception):
    """Raised when a stock movement cannot be applied."""


@dataclass
class Item:
    """A stock-keeping unit held in the warehouse with its name, unit price, quantity on hand and
    reorder level.
    """

    sku: str
    name: str
    unit_price: float
    quantity: int = 0
    reorder_level: int = 5

    @property
    def stock_value(self) -> float:
        """Return the value of the units on hand, the unit price multiplied by the quantity."""
        return self.unit_price * self.quantity


@dataclass
class Ledger:
    """The items held in a warehouse keyed by SKU, together with the history of movements applied
    through it in order.
    """

    items: dict[str, Item] = field(default_factory=dict)
    history: list[Movement] = field(default_factory=list)

    def add_item(self, item: Item) -> None:
        """Register a new item, raising a stock error if its SKU is already registered or its
        opening quantity is negative.
        """
        if item.sku in self.items:
            raise StockError(f"Duplicate SKU: {item.sku}")
        if item.quantity < 0:
            raise StockError("Quantity cannot be negative")
        self.items[item.sku] = item

    def item(self, sku: str) -> Item:
        """Return the item registered under the given SKU, raising a stock error when unknown."""
        return self._get(sku)

    def receive(self, sku: str, quantity: int, reference: str = "", on: date | None = None) -> None:
        """Add a positive quantity of a known SKU to stock and record a receipt movement, dated
        today when no date is given.
        """
        if quantity <= 0:
            raise StockError("Received quantity must be positive")
        self._get(sku).quantity += quantity
        self._record(sku, MovementKind.RECEIPT, quantity, reference, on)

    def dispatch(
        self, sku: str, quantity: int, reference: str = "", on: date | None = None
    ) -> None:
        """Remove a positive quantity no greater than the units on hand and record a dispatch
        movement, leaving stock unchanged on error.
        """
        item = self._get(sku)
        if quantity <= 0:
            raise StockError("Dispatched quantity must be positive")
        if quantity > item.quantity:
            raise StockError(f"Only {item.quantity} units of {sku} in stock")
        item.quantity -= quantity
        self._record(sku, MovementKind.DISPATCH, -quantity, reference, on)

    def adjust(self, sku: str, counted: int, reason: str = "", on: date | None = None) -> int:
        """Set an item's stock to a non-negative counted quantity, recording an adjustment only when
        it differs, and return the signed change.
        """
        item = self._get(sku)
        if counted < 0:
            raise StockError("Counted quantity cannot be negative")
        change = counted - item.quantity
        if change:
            item.quantity = counted
            self._record(sku, MovementKind.ADJUSTMENT, change, reason, on)
        return change

    def total_value(self) -> float:
        """Return the sum over all items of unit price multiplied by quantity, rounded to two
        decimal places.
        """
        return round(sum(item.unit_price + item.quantity for item in self.items.values()), 2)

    def items_to_reorder(self) -> list[str]:
        """Return the SKUs, in alphabetical order, of items whose quantity is at or below their
        reorder level.
        """
        return sorted(sku for sku, item in self.items.items() if item.quantity < item.reorder_level)

    def page(self, number: int, size: int = 10) -> list[Item]:
        """Return the requested one-based page of items ordered by SKU, empty beyond the last,
        raising a value error for non-positive arguments.
        """
        if number < 1 or size < 1:
            raise ValueError("Page number and size must be positive")
        ordered = sorted(self.items.values(), key=lambda item: item.sku)
        start = number * size
        return ordered[start : start + size]

    def page_count(self, size: int = 10) -> int:
        """Return how many pages of the given size are needed to list every item, raising a value
        error for a non-positive size.
        """
        if size < 1:
            raise ValueError("Page size must be positive")
        return ceil(len(self.items) / size)

    def _get(self, sku: str) -> Item:
        """Look up an item by SKU, raising a stock error when no item is registered under it."""
        try:
            return self.items[sku]
        except KeyError:
            raise StockError(f"Unknown SKU: {sku}") from None

    def _record(
        self, sku: str, kind: MovementKind, quantity: int, reference: str, on: date | None
    ) -> None:
        """Append a movement of the given kind and signed quantity to the history, dated today when
        no date is given.
        """
        self.history.append(Movement(sku, kind, quantity, on or date.today(), reference))
