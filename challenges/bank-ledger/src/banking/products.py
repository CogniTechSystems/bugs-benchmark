"""Account products: the terms an account is opened under."""

from dataclasses import dataclass
from decimal import Decimal

from banking.money import ZERO, to_money


@dataclass(frozen=True)
class AccountProduct:
    """The overdraft limit, monthly fee and waiver threshold, annual interest rate and optional
    daily withdrawal limit that apply to every account of one product.
    """

    name: str
    overdraft_limit: Decimal = ZERO
    monthly_fee: Decimal = ZERO
    fee_waiver_threshold: Decimal = ZERO
    annual_rate_percent: Decimal = Decimal("0")
    daily_withdrawal_limit: Decimal | None = None

    def __post_init__(self) -> None:
        """Validate the terms, raising ValueError for a blank name or any negative value."""
        if not self.name.strip():
            raise ValueError("Product name must not be blank")
        amounts = [self.overdraft_limit, self.monthly_fee, self.fee_waiver_threshold]
        if self.daily_withdrawal_limit is not None:
            amounts.append(self.daily_withdrawal_limit)
        if any(amount < 0 for amount in amounts) or self.annual_rate_percent < 0:
            raise ValueError(f"Product {self.name} has negative terms")

    @property
    def pays_interest(self) -> bool:
        """Whether accounts of this product earn interest at a positive rate."""
        return self.annual_rate_percent > 0


CHECKING = AccountProduct(
    name="checking",
    overdraft_limit=to_money("500"),
    monthly_fee=to_money("2.50"),
    fee_waiver_threshold=to_money("1000"),
    daily_withdrawal_limit=to_money("2000"),
)

SAVINGS = AccountProduct(
    name="savings",
    annual_rate_percent=Decimal("2.4"),
    daily_withdrawal_limit=to_money("500"),
)

STANDARD_PRODUCTS = {product.name: product for product in (CHECKING, SAVINGS)}
