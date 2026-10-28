"""Monthly account servicing: fees, interest and statements."""

import csv
import io
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from banking.accounts import Account, Transaction
from banking.money import ZERO, format_money, percentage_of, sum_money, to_money


def charge_monthly_fee(
    account: Account,
    fee: str | Decimal = "2.50",
    waiver_threshold: str | Decimal = "1000.00",
    posted_on: date | None = None,
) -> Decimal:
    """Debit and return the fee unless the balance reaches the waiver threshold, charging it even
    into overdraft and returning zero when waived.
    """
    if account.balance >= to_money(waiver_threshold):
        return ZERO
    charged = to_money(fee)
    account.record("fee", charged, "Monthly fee", posted_on)
    return charged


def apply_interest(
    account: Account, annual_rate_percent: str | Decimal, posted_on: date | None = None
) -> Decimal:
    """Credit and return a month of interest at a twelfth of the annual rate, rounded half away from
    zero, or zero for a non-positive balance.
    """
    if account.balance <= 0:
        return ZERO
    interest = percentage_of(account.balance, Decimal(annual_rate_percent) / 12)
    if interest > 0:
        account.record("interest", interest, "Monthly interest", posted_on)
    return interest


def statement_lines(account: Account) -> list[str]:
    """Render each transaction in the history as a fixed-width line of kind, signed amount and
    running balance.
    """
    lines = []
    running = ZERO
    for transaction in account.history:
        running += transaction.signed_amount
        amount = format_money(transaction.signed_amount)
        lines.append(f"{transaction.kind:<12} {amount:>12} {format_money(running):>12}")
    return lines


@dataclass(frozen=True)
class Statement:
    """An account's opening balance and the transactions posted within one inclusive statement
    period.
    """

    account_id: str
    start: date
    end: date
    opening_balance: Decimal
    transactions: tuple[Transaction, ...]

    @property
    def total_credits(self) -> Decimal:
        """Return the sum of the credits posted in the period as a positive amount."""
        return sum_money(entry.amount for entry in self.transactions if entry.is_credit)

    @property
    def total_debits(self) -> Decimal:
        """Return the sum of the debits posted in the period as a positive amount."""
        return sum_money(entry.amount for entry in self.transactions if not entry.is_credit)

    @property
    def interest_earned(self) -> Decimal:
        """Return the interest credited to the account during the period."""
        return sum_money(entry.amount for entry in self.transactions if entry.kind == "interest")

    @property
    def closing_balance(self) -> Decimal:
        """Return the opening balance plus the period's credits minus its debits."""
        return self.opening_balance + self.total_credits - self.total_debits


def build_statement(account: Account, start: date, end: date) -> Statement:
    """Build the statement for the inclusive period, opening at the balance before it starts,
    raising ValueError if it ends before it starts.
    """
    if end < start:
        raise ValueError("Statement period ends before it starts")
    return Statement(
        account_id=account.account_id,
        start=start,
        end=end,
        opening_balance=account.balance_at(start - timedelta(days=1)),
        transactions=tuple(account.transactions_between(start, end)),
    )


def average_daily_balance(account: Account, start: date, end: date) -> Decimal:
    """Return the mean daily closing balance over the inclusive period, rounded half away from zero,
    raising ValueError if it ends before it starts.
    """
    if end < start:
        raise ValueError("Period ends before it starts")
    days = (end - start).days + 1
    total = sum(
        (account.balance_at(start + timedelta(days=offset)) for offset in range(days)), ZERO
    )
    return to_money(total / days)


def export_csv(statement: Statement) -> str:
    """Export the statement as CSV with a header row of ISO date, kind, reference, signed amount and
    running balance in plain two-decimal notation.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["date", "kind", "reference", "amount", "balance"])
    running = statement.opening_balance
    for entry in statement.transactions:
        running += entry.signed_amount
        writer.writerow(
            [
                entry.posted_on.isoformat(),
                entry.kind,
                entry.reference,
                f"{entry.signed_amount:.2f}",
                f"{running:.2f}",
            ]
        )
    return buffer.getvalue()
