"""Stock movement records and queries over a movement history."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class MovementKind(StrEnum):
    """The reason a stock level changed."""

    RECEIPT = "receipt"
    DISPATCH = "dispatch"
    ADJUSTMENT = "adjustment"


@dataclass(frozen=True)
class Movement:
    """A single dated change to one SKU's stock, whose signed quantity is positive for stock in and
    negative for stock out.
    """

    sku: str
    kind: MovementKind
    quantity: int
    on: date
    reference: str = ""

    @property
    def is_inbound(self) -> bool:
        """Return True if the movement increased stock, meaning its signed quantity is positive."""
        return self.quantity > 0


def movements_for(history: Iterable[Movement], sku: str) -> list[Movement]:
    """Return the movements of a SKU from the history in their original order."""
    return [movement for movement in history if movement.sku == sku]


def movements_between(history: Iterable[Movement], start: date, end: date) -> list[Movement]:
    """Return movements dated from start to end inclusive in original order, raising a value error
    if start is after end.
    """
    if start > end:
        raise ValueError("Start date must not be after end date")
    return [movement for movement in history if start <= movement.on <= end]


def net_change(history: Iterable[Movement], sku: str) -> int:
    """Return the overall signed change in stock of a SKU across the history, zero if it has no
    movements.
    """
    return sum(movement.quantity for movement in movements_for(history, sku))


def totals_by_kind(history: Iterable[Movement]) -> dict[MovementKind, int]:
    """Return the signed unit total for every movement kind, with zero for kinds that have no
    movements.
    """
    totals = dict.fromkeys(MovementKind, 0)
    for movement in history:
        totals[movement.kind] += movement.quantity
    return totals
