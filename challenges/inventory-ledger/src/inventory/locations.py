"""Bin locations within the warehouse and the stock placed in them."""

from dataclasses import dataclass, field

from inventory.ledger import Ledger


class LocationError(Exception):
    """Raised when stock cannot be placed at or taken from a location."""


@dataclass(frozen=True, order=True)
class Location:
    """A storage bin identified by aisle, shelf and bin, ordered by aisle, then shelf, then bin in
    warehouse walking order.
    """

    aisle: str
    shelf: int
    bin: int

    @classmethod
    def parse(cls, code: str) -> "Location":
        """Build a location from its aisle-shelf-bin text form, uppercasing the aisle and raising a
        location error for malformed codes.
        """
        parts = code.strip().split("-")
        if len(parts) != 3 or not parts[0] or not all(part.isdigit() for part in parts[1:]):
            raise LocationError(f"Invalid location code: {code!r}")
        return cls(parts[0].upper(), int(parts[1]), int(parts[2]))

    def __str__(self) -> str:
        """Return the aisle-shelf-bin text form of the location, with the shelf zero-padded to two
        digits.
        """
        return f"{self.aisle}-{self.shelf:02d}-{self.bin}"


@dataclass
class StockMap:
    """How many units of each SKU are stored at each location."""

    placements: dict[Location, dict[str, int]] = field(default_factory=dict)

    def put(self, location: Location, sku: str, quantity: int) -> None:
        """Place a positive quantity of a SKU at a location, adding to any units held there."""
        if quantity <= 0:
            raise LocationError("Placed quantity must be positive")
        bin_stock = self.placements.setdefault(location, {})
        bin_stock[sku] = bin_stock.get(sku, 0) + quantity

    def take(self, location: Location, sku: str, quantity: int) -> None:
        """Remove a positive quantity no greater than the units held at a location, forgetting SKUs
        and locations left empty.
        """
        if quantity <= 0:
            raise LocationError("Taken quantity must be positive")
        held = self.quantity_at(location, sku)
        if quantity > held:
            raise LocationError(f"Only {held} units of {sku} at {location}")
        bin_stock = self.placements[location]
        if quantity == held:
            del bin_stock[sku]
            if not bin_stock:
                del self.placements[location]
        else:
            bin_stock[sku] = held - quantity

    def move(self, source: Location, target: Location, sku: str, quantity: int) -> None:
        """Transfer a quantity of a SKU between two locations, changing nothing if it cannot be
        taken from the source.
        """
        self.take(source, sku, quantity)
        self.put(target, sku, quantity)

    def quantity_at(self, location: Location, sku: str) -> int:
        """Return the units of a SKU held at a location, zero if there are none."""
        return self.placements.get(location, {}).get(sku, 0)

    def locations_of(self, sku: str) -> list[Location]:
        """Return the locations holding a SKU, sorted in warehouse walking order."""
        return sorted(location for location, stock in self.placements.items() if sku in stock)

    def total_for(self, sku: str) -> int:
        """Return the units of a SKU held across all locations, zero if it is placed nowhere."""
        return sum(stock.get(sku, 0) for stock in self.placements.values())

    def discrepancies(self, ledger: Ledger) -> dict[str, int]:
        """Return, ordered by SKU, each nonzero ledger quantity minus placed total, treating placed
        but unregistered SKUs as recorded zero.
        """
        skus = set(ledger.items).union(*self.placements.values())
        recorded = {sku: ledger.items[sku].quantity if sku in ledger.items else 0 for sku in skus}
        differences = {sku: recorded[sku] - self.total_for(sku) for sku in sorted(skus)}
        return {sku: difference for sku, difference in differences.items() if difference}
