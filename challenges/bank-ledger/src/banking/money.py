"""Monetary amounts represented as Decimal values rounded to whole cents."""

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value: str | int | Decimal) -> Decimal:
    """Convert a string, integer or Decimal to cents with halves rounded away from zero, rejecting
    floats with TypeError.
    """
    if isinstance(value, float):
        raise TypeError("Use strings or Decimals for money, not floats")
    try:
        return Decimal(value).quantize(CENT)
    except InvalidOperation:
        raise ValueError(f"Invalid amount: {value!r}") from None


def percentage_of(amount: Decimal, percent: Decimal) -> Decimal:
    """Return the given percentage points of the amount, rounded to cents with halves away from
    zero.
    """
    return (amount * percent / 100).quantize(CENT, rounding=ROUND_HALF_UP)


def format_money(amount: Decimal, symbol: str = "") -> str:
    """Format the amount rounded to cents with thousands separators, two decimal places and any
    minus sign placed before the currency symbol.
    """
    value = to_money(amount)
    sign = "-" if value < 0 else ""
    return f"{sign}{symbol}{abs(value):,.2f}"


def sum_money(amounts: Iterable[Decimal]) -> Decimal:
    """Return the total of the amounts rounded to cents, or zero for an empty iterable."""
    return to_money(sum(amounts, ZERO))


def allocate(amount: Decimal, parts: int) -> list[Decimal]:
    """Split the amount into a positive number of shares differing by at most a cent and summing to
    it, with leftover cents going to the earliest shares.
    """
    if parts <= 0:
        raise ValueError("parts must be positive")
    cents = int(to_money(amount) / CENT)
    share, remainder = divmod(abs(cents), parts)
    sign = -1 if cents < 0 else 1
    return [
        Decimal(sign * (share + (1 if index < remainder else 0))) * CENT for index in range(parts)
    ]
