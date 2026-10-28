"""Customer accounts, their ledger transactions and movements of money between accounts."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from banking.money import ZERO, to_money

CREDIT_KINDS = frozenset({"deposit", "transfer_in"})
DEBIT_KINDS = frozenset({"withdrawal", "transfer_out", "fee", "interest"})


class InsufficientFundsError(Exception):
    """Raised when a debit would take an account beyond its available funds."""


@dataclass(frozen=True)
class Transaction:
    """An immutable ledger entry whose unsigned amount is a credit for deposits, incoming transfers
    and interest, and a debit for withdrawals, outgoing transfers and fees.
    """

    kind: str
    amount: Decimal
    reference: str = ""
    posted_on: date = field(default_factory=date.today)

    def __post_init__(self) -> None:
        """Reject a kind that is neither a credit kind nor a debit kind by raising ValueError."""
        if self.kind not in CREDIT_KINDS | DEBIT_KINDS:
            raise ValueError(f"Unknown transaction kind: {self.kind}")

    @property
    def is_credit(self) -> bool:
        """Whether this entry is of a credit kind and so adds to the account balance."""
        return self.kind in CREDIT_KINDS

    @property
    def signed_amount(self) -> Decimal:
        """Return the amount signed positive for credits and negative for debits."""
        return self.amount if self.kind in CREDIT_KINDS else -self.amount


class Account:
    """A customer account with an overdraft limit and its own transaction history, from which the
    balance is always derived.
    """

    def __init__(
        self,
        account_id: str,
        overdraft_limit: str | Decimal = "0",
        history: list[Transaction] = [],
    ) -> None:
        self.account_id = account_id
        self.overdraft_limit = to_money(overdraft_limit)
        self.history = history

    @property
    def balance(self) -> Decimal:
        """Return the sum of the signed amounts of every transaction in the history."""
        return sum((transaction.signed_amount for transaction in self.history), Decimal("0.00"))

    def available(self) -> Decimal:
        """Return the most that can be debited now, the balance plus the overdraft limit."""
        return self.balance + self.overdraft_limit

    def deposit(
        self, amount: str | Decimal, reference: str = "", posted_on: date | None = None
    ) -> Transaction:
        """Credit a positive amount rounded to cents and return the transaction, raising ValueError
        for a non-positive amount.
        """
        return self.record("deposit", _positive(amount), reference, posted_on)

    def withdraw(
        self, amount: str | Decimal, reference: str = "", posted_on: date | None = None
    ) -> Transaction:
        """Debit a positive amount within the available funds and return the transaction, otherwise
        raising an insufficient funds error and leaving the account unchanged.
        """
        value = _positive(amount)
        if value > self.available():
            raise InsufficientFundsError(f"Account {self.account_id} has insufficient funds")
        return self.record("withdrawal", value, reference, posted_on)

    def record(
        self, kind: str, amount: Decimal, reference: str = "", posted_on: date | None = None
    ) -> Transaction:
        """Append and return a transaction posted on the given date or today, without validating the
        amount or the available funds.
        """
        transaction = Transaction(kind, amount, reference, posted_on or date.today())
        self.history.append(transaction)
        return transaction

    def transactions_between(self, start: date, end: date) -> list[Transaction]:
        """Return the transactions posted from the start date to the end date inclusive, in posting
        order.
        """
        return [entry for entry in self.history if start <= entry.posted_on <= end]

    def balance_at(self, day: date) -> Decimal:
        """Return the balance at the close of the given day, counting only entries posted on or
        before it.
        """
        return sum((entry.signed_amount for entry in self.history if entry.posted_on <= day), ZERO)

    def debited_on(self, day: date, kinds: Iterable[str]) -> Decimal:
        """Return the total amount of the entries of the given kinds posted on the given day."""
        wanted = frozenset(kinds)
        return sum(
            (
                entry.amount
                for entry in self.history
                if entry.posted_on == day and entry.kind in wanted
            ),
            ZERO,
        )


def transfer(source: Account, target: Account, amount: str | Decimal, reference: str = "") -> None:
    """Atomically move a positive amount between two different accounts within the source's
    available funds, changing neither on failure.
    """
    if source is target:
        raise ValueError("Cannot transfer to the same account")
    value = _positive(amount)
    source.record("transfer_out", value, reference)
    if source.available() < 0:
        raise InsufficientFundsError(f"Account {source.account_id} has insufficient funds")
    target.record("transfer_in", value, reference)


def _positive(amount: str | Decimal) -> Decimal:
    """Return the amount rounded to cents, raising ValueError unless it is positive."""
    value = to_money(amount)
    if value <= 0:
        raise ValueError("Amount must be positive")
    return value
