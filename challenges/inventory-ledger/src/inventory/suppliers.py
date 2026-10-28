"""Suppliers and the purchase orders that replenish stock."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

from inventory.ledger import Ledger, StockError


@dataclass(frozen=True)
class Supplier:
    """A vendor that stock is bought from, with a unique code, trading name and delivery lead time
    in days.
    """

    code: str
    name: str
    lead_time_days: int = 7


@dataclass(frozen=True)
class OrderLine:
    """A quantity of one SKU ordered at an agreed unit cost."""

    sku: str
    quantity: int
    unit_cost: float

    @property
    def line_total(self) -> float:
        """Return the cost of the line, the unit cost multiplied by the quantity."""
        return self.unit_cost * self.quantity


class OrderStatus(StrEnum):
    """How far delivery of a purchase order has progressed."""

    OPEN = "open"
    PARTIAL = "partial"
    RECEIVED = "received"


@dataclass
class PurchaseOrder:
    """An order placed with a supplier, tracking which units have been delivered."""

    number: str
    supplier: Supplier
    ordered_on: date
    lines: list[OrderLine] = field(default_factory=list)
    received: dict[str, int] = field(default_factory=dict)

    def add_line(self, sku: str, quantity: int, unit_cost: float) -> OrderLine:
        """Append and return a line for a SKU not yet on the order, raising a value error for non-
        positive quantity or negative cost.
        """
        if quantity <= 0:
            raise ValueError("Ordered quantity must be positive")
        if unit_cost < 0:
            raise ValueError("Unit cost cannot be negative")
        if any(line.sku == sku for line in self.lines):
            raise ValueError(f"{sku} is already on order {self.number}")
        line = OrderLine(sku, quantity, unit_cost)
        self.lines.append(line)
        return line

    @property
    def expected_on(self) -> date:
        """Return the expected delivery date, the order date plus the supplier lead time in days."""
        return self.ordered_on + timedelta(days=self.supplier.lead_time_days)

    def total_cost(self) -> float:
        """Return the cost of every line on the order, rounded to two decimal places."""
        return round(sum(line.line_total for line in self.lines), 2)

    def outstanding(self, sku: str) -> int:
        """Return the units of a SKU ordered but not yet received, zero if not on the order."""
        ordered = sum(line.quantity for line in self.lines if line.sku == sku)
        return ordered - self.received.get(sku, 0)

    @property
    def status(self) -> OrderStatus:
        """Return open before any delivery, received once every line is complete, and partial
        otherwise.
        """
        if not any(self.received.values()):
            return OrderStatus.OPEN
        if all(self.outstanding(line.sku) == 0 for line in self.lines):
            return OrderStatus.RECEIVED
        return OrderStatus.PARTIAL

    def receive(self, ledger: Ledger, sku: str, quantity: int, on: date | None = None) -> None:
        """Book a delivery of at most the outstanding units of a SKU into a ledger under the order
        number, recording nothing on error.
        """
        if quantity <= 0:
            raise StockError("Received quantity must be positive")
        outstanding = self.outstanding(sku)
        if quantity > outstanding:
            raise StockError(f"Only {outstanding} units of {sku} outstanding on {self.number}")
        ledger.receive(sku, quantity, reference=self.number, on=on)
        self.received[sku] = self.received.get(sku, 0) + quantity


def draft_order(ledger: Ledger, supplier: Supplier, number: str, ordered_on: date) -> PurchaseOrder:
    """Draft an order topping each item due for reordering up to twice its reorder level at unit
    price, skipping zero reorder levels.
    """
    order = PurchaseOrder(number, supplier, ordered_on)
    for sku in ledger.items_to_reorder():
        item = ledger.item(sku)
        if item.reorder_level > 0:
            order.add_line(sku, 2 * item.reorder_level - item.quantity, item.unit_price)
    return order
