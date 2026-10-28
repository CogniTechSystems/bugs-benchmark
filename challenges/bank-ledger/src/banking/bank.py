"""A bank that opens accounts under products and audits every operation on them."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from banking.accounts import Account, InsufficientFundsError, Transaction, transfer
from banking.audit import REJECTED, AuditLog
from banking.money import ZERO, sum_money, to_money
from banking.products import STANDARD_PRODUCTS, AccountProduct
from banking.statements import apply_interest, charge_monthly_fee


class AccountNotFoundError(LookupError):
    """Raised when an operation names an account the bank does not hold."""


class WithdrawalLimitError(Exception):
    """Raised when a withdrawal would exceed the product's daily withdrawal limit."""


@dataclass(frozen=True)
class MonthEndResult:
    """The fee charged and the interest credited to one account by month-end servicing."""

    fee: Decimal
    interest: Decimal


class Bank:
    """Holds accounts keyed by id together with the product each was opened under, and audits every
    operation on them.
    """

    def __init__(self, products: Mapping[str, AccountProduct] | None = None) -> None:
        self.products = dict(STANDARD_PRODUCTS if products is None else products)
        self.audit = AuditLog()
        self._accounts: dict[str, Account] = {}
        self._products: dict[str, AccountProduct] = {}

    def open_account(
        self,
        account_id: str,
        product_name: str,
        opening_deposit: str | Decimal | None = None,
        opened_on: date | None = None,
    ) -> Account:
        """Open an empty account with the product's overdraft limit, crediting any opening deposit,
        raising ValueError for a duplicate id or unknown product.
        """
        if account_id in self._accounts:
            raise ValueError(f"Account {account_id} already exists")
        if product_name not in self.products:
            raise ValueError(f"Unknown product: {product_name}")
        product = self.products[product_name]
        account = Account(account_id, product.overdraft_limit)
        self._accounts[account_id] = account
        self._products[account_id] = product
        self.audit.record("open", account_id, detail=product_name)
        if opening_deposit is not None:
            self.deposit(account_id, opening_deposit, "Opening deposit", opened_on)
        return account

    def account(self, account_id: str) -> Account:
        """Return the account with the given id, raising a not-found error when the bank holds no
        such account.
        """
        try:
            return self._accounts[account_id]
        except KeyError:
            raise AccountNotFoundError(account_id) from None

    def product(self, account_id: str) -> AccountProduct:
        """Return the product the given account was opened under."""
        self.account(account_id)
        return self._products[account_id]

    def accounts(self) -> list[Account]:
        """Return every open account in the order the accounts were opened."""
        return list(self._accounts.values())

    def close_account(self, account_id: str) -> None:
        """Close an account whose balance is exactly zero, otherwise raising ValueError and keeping
        it open.
        """
        account = self.account(account_id)
        if account.balance != 0:
            raise ValueError(f"Account {account_id} must have a zero balance to close")
        del self._accounts[account_id]
        del self._products[account_id]
        self.audit.record("close", account_id)

    def deposit(
        self,
        account_id: str,
        amount: str | Decimal,
        reference: str = "",
        posted_on: date | None = None,
    ) -> Transaction:
        """Credit the amount to the account, audit it as accepted and return the transaction."""
        transaction = self.account(account_id).deposit(amount, reference, posted_on)
        self.audit.record("deposit", account_id, transaction.amount)
        return transaction

    def withdraw(
        self,
        account_id: str,
        amount: str | Decimal,
        reference: str = "",
        posted_on: date | None = None,
    ) -> Transaction:
        """Debit the amount within the available funds and the daily limit, counting that day's
        earlier withdrawals, auditing any rejection and leaving the account unchanged.
        """
        account = self.account(account_id)
        limit = self.product(account_id).daily_withdrawal_limit
        value = to_money(amount)
        day = posted_on or date.today()
        if limit is not None and account.debited_on(day, {"withdrawal"}) + value > limit:
            self.audit.record("withdraw", account_id, value, REJECTED, "daily limit")
            raise WithdrawalLimitError(f"Account {account_id} exceeds its daily limit")
        try:
            transaction = account.withdraw(value, reference, day)
        except InsufficientFundsError:
            self.audit.record("withdraw", account_id, value, REJECTED, "insufficient funds")
            raise
        self.audit.record("withdraw", account_id, value)
        return transaction

    def transfer(
        self, source_id: str, target_id: str, amount: str | Decimal, reference: str = ""
    ) -> None:
        """Atomically move the amount between two held accounts and audit the outcome, so a rejected
        attempt leaves both balances unchanged.
        """
        source, target = self.account(source_id), self.account(target_id)
        value = to_money(amount)
        try:
            transfer(source, target, value, reference)
        except InsufficientFundsError:
            self.audit.record("transfer", source_id, value, REJECTED, f"to {target_id}")
            raise
        self.audit.record("transfer", source_id, value, detail=f"to {target_id}")

    def run_month_end(self, on: date | None = None) -> dict[str, MonthEndResult]:
        """Charge each account its product's monthly fee, then credit interest on the remaining
        balance, returning the fee and interest per account id.
        """
        results: dict[str, MonthEndResult] = {}
        for account_id, account in self._accounts.items():
            product = self._products[account_id]
            fee = ZERO
            if product.monthly_fee > 0:
                fee = charge_monthly_fee(
                    account, product.monthly_fee, product.fee_waiver_threshold, on
                )
            interest = apply_interest(account, product.annual_rate_percent, on)
            results[account_id] = MonthEndResult(fee, interest)
            self.audit.record("month_end", account_id, detail=f"fee {fee}, interest {interest}")
        return results

    def total_balance(self) -> Decimal:
        """Return the sum of the balances of every open account, overdrafts included."""
        return sum_money(account.balance for account in self._accounts.values())
