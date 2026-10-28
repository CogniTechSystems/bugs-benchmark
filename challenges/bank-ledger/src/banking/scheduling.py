"""Recurring payments between accounts held by a bank."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from banking.accounts import InsufficientFundsError
from banking.bank import Bank
from banking.money import to_money


class Frequency(Enum):
    """How often a scheduled payment recurs."""

    WEEKLY = "weekly"
    MONTHLY = "monthly"


def add_months(day: date, months: int) -> date:
    """Return the date the given number of calendar months after the day, clamped to the last day of
    a shorter target month.
    """
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def next_occurrence(day: date, frequency: Frequency) -> date:
    """Return the due date one week or one calendar month after the day, by its frequency."""
    if frequency is Frequency.WEEKLY:
        return day + timedelta(weeks=1)
    return add_months(day, 1)


@dataclass
class ScheduledPayment:
    """A standing order paying a fixed amount between two accounts on a recurring schedule, tracking
    its next due date, consecutive failures and whether it is active.
    """

    payment_id: int
    source_id: str
    target_id: str
    amount: Decimal
    next_due: date
    frequency: Frequency
    failures: int = 0
    active: bool = True


@dataclass(frozen=True)
class PaymentOutcome:
    """The result of one attempt to pay an instalment."""

    payment_id: int
    due_on: date
    succeeded: bool
    detail: str = ""


class PaymentScheduler:
    """Runs scheduled payments through a bank, suspending a payment after a set number of
    consecutive failures.
    """

    def __init__(self, bank: Bank, max_failures: int = 3) -> None:
        if max_failures < 1:
            raise ValueError("max_failures must be at least 1")
        self.bank = bank
        self.max_failures = max_failures
        self._payments: dict[int, ScheduledPayment] = {}

    def schedule(
        self,
        source_id: str,
        target_id: str,
        amount: str | Decimal,
        first_due: date,
        frequency: Frequency = Frequency.MONTHLY,
    ) -> ScheduledPayment:
        """Register and return a payment numbered after the existing ones, raising ValueError for
        identical accounts or a non-positive amount.
        """
        self.bank.account(source_id)
        self.bank.account(target_id)
        if source_id == target_id:
            raise ValueError("A payment needs two different accounts")
        value = to_money(amount)
        if value <= 0:
            raise ValueError("Amount must be positive")
        payment_id = len(self._payments) + 1
        payment = ScheduledPayment(payment_id, source_id, target_id, value, first_due, frequency)
        self._payments[payment_id] = payment
        return payment

    def cancel(self, payment_id: int) -> None:
        """Stop attempting the payment, raising KeyError for an unknown id."""
        self._payments[payment_id].active = False

    def due(self, on: date) -> list[ScheduledPayment]:
        """Return the active payments due on or before the date, earliest first."""
        pending = [p for p in self._payments.values() if p.active and p.next_due <= on]
        return sorted(pending, key=lambda payment: (payment.next_due, payment.payment_id))

    def run(self, on: date) -> list[PaymentOutcome]:
        """Attempt each due payment once, advancing a success by one period and keeping a failure
        due for retry until it reaches the failure limit.
        """
        outcomes = []
        for payment in self.due(on):
            due_on = payment.next_due
            try:
                self.bank.transfer(
                    payment.source_id,
                    payment.target_id,
                    payment.amount,
                    f"Standing order {payment.payment_id}",
                )
            except InsufficientFundsError:
                payment.failures += 1
                if payment.failures >= self.max_failures:
                    payment.active = False
                outcomes.append(
                    PaymentOutcome(payment.payment_id, due_on, False, "insufficient funds")
                )
                continue
            payment.failures = 0
            payment.next_due = next_occurrence(due_on, payment.frequency)
            outcomes.append(PaymentOutcome(payment.payment_id, due_on, True))
        return outcomes
