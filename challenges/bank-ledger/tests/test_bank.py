from datetime import date
from decimal import Decimal

import pytest
from banking import (
    CHECKING,
    SAVINGS,
    Account,
    AccountNotFoundError,
    AccountProduct,
    AuditLog,
    Bank,
    Frequency,
    InsufficientFundsError,
    MonthEndResult,
    PaymentScheduler,
    WithdrawalLimitError,
    add_months,
    allocate,
    average_daily_balance,
    build_statement,
    export_csv,
    format_money,
    sum_money,
    to_money,
)

JAN_1 = date(2024, 1, 1)
JAN_15 = date(2024, 1, 15)
JAN_31 = date(2024, 1, 31)
FEB_1 = date(2024, 2, 1)


def make_account(account_id: str = "A", overdraft_limit: str = "0") -> Account:
    return Account(account_id, overdraft_limit, history=[])


def test_format_money_with_symbol():
    assert format_money(Decimal("-1234.5"), "$") == "-$1,234.50"
    assert format_money(Decimal("0"), "EUR ") == "EUR 0.00"
    assert format_money(Decimal("1000000")) == "1,000,000.00"


def test_sum_money():
    assert sum_money([]) == Decimal("0.00")
    assert sum_money([Decimal("1.10"), Decimal("2.20")]) == Decimal("3.30")


def test_allocate_spreads_leftover_cents():
    assert allocate(Decimal("10.00"), 3) == [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")]
    assert allocate(Decimal("-0.05"), 2) == [Decimal("-0.03"), Decimal("-0.02")]
    assert sum(allocate(Decimal("99.99"), 7)) == Decimal("99.99")


def test_allocate_rejects_non_positive_parts():
    with pytest.raises(ValueError):
        allocate(Decimal("1"), 0)


def test_transaction_rejects_unknown_kind():
    account = make_account()
    with pytest.raises(ValueError):
        account.record("refund", Decimal("1.00"))


def test_transaction_direction():
    account = make_account()
    deposit = account.deposit("5", posted_on=JAN_1)
    withdrawal = account.withdraw("2", posted_on=JAN_1)
    assert deposit.is_credit and deposit.signed_amount == Decimal("5.00")
    assert not withdrawal.is_credit and withdrawal.signed_amount == Decimal("-2.00")
    assert deposit.posted_on == JAN_1


def test_balance_at_and_transactions_between():
    account = make_account()
    account.deposit("100", posted_on=JAN_1)
    account.withdraw("40", posted_on=JAN_15)
    account.deposit("10", posted_on=FEB_1)
    assert account.balance_at(date(2023, 12, 31)) == Decimal("0.00")
    assert account.balance_at(JAN_15) == Decimal("60.00")
    assert [entry.kind for entry in account.transactions_between(JAN_1, JAN_31)] == [
        "deposit",
        "withdrawal",
    ]


def test_debited_on_counts_only_requested_kinds_on_that_day():
    account = make_account()
    account.deposit("100", posted_on=JAN_1)
    account.withdraw("10", posted_on=JAN_1)
    account.withdraw("5", posted_on=JAN_15)
    account.record("fee", Decimal("1.00"), posted_on=JAN_1)
    assert account.debited_on(JAN_1, {"withdrawal"}) == Decimal("10.00")
    assert account.debited_on(JAN_1, {"withdrawal", "fee"}) == Decimal("11.00")


def test_product_rejects_invalid_terms():
    with pytest.raises(ValueError):
        AccountProduct(name=" ")
    with pytest.raises(ValueError):
        AccountProduct(name="bad", monthly_fee=Decimal("-1"))
    assert SAVINGS.pays_interest and not CHECKING.pays_interest


def test_audit_log_sequence_and_filters():
    log = AuditLog()
    log.record("deposit", "A", Decimal("1.00"))
    log.record("withdraw", "B", Decimal("2.00"), "rejected", "insufficient funds")
    assert [entry.sequence for entry in log] == [1, 2]
    assert len(log) == 2
    assert [entry.account_id for entry in log.rejected()] == ["B"]
    assert [entry.action for entry in log.for_account("A")] == ["deposit"]
    with pytest.raises(ValueError):
        log.record("deposit", "A", outcome="maybe")


def test_open_account_applies_product_terms():
    bank = Bank()
    checking = bank.open_account("C1", "checking", "250", JAN_1)
    savings = bank.open_account("S1", "savings")
    assert checking.overdraft_limit == Decimal("500.00")
    assert checking.balance == Decimal("250.00")
    assert savings.history == []
    assert bank.product("S1") is SAVINGS
    assert [account.account_id for account in bank.accounts()] == ["C1", "S1"]
    assert [entry.action for entry in bank.audit.for_account("C1")] == ["open", "deposit"]


def test_open_account_rejects_duplicates_and_unknown_products():
    bank = Bank()
    bank.open_account("C1", "checking")
    with pytest.raises(ValueError):
        bank.open_account("C1", "checking")
    with pytest.raises(ValueError):
        bank.open_account("C2", "premium")


def test_unknown_account_raises():
    with pytest.raises(AccountNotFoundError):
        Bank().account("missing")


def test_close_account_requires_zero_balance():
    bank = Bank()
    bank.open_account("C1", "checking", "10")
    with pytest.raises(ValueError):
        bank.close_account("C1")
    bank.withdraw("C1", "10")
    bank.close_account("C1")
    with pytest.raises(AccountNotFoundError):
        bank.account("C1")


def test_withdrawal_daily_limit():
    bank = Bank()
    bank.open_account("S1", "savings", "2000", JAN_1)
    bank.withdraw("S1", "300", posted_on=JAN_15)
    with pytest.raises(WithdrawalLimitError):
        bank.withdraw("S1", "200.01", posted_on=JAN_15)
    bank.withdraw("S1", "200", posted_on=JAN_15)
    bank.withdraw("S1", "500", posted_on=FEB_1)
    assert bank.account("S1").balance == Decimal("1000.00")
    assert bank.audit.rejected()[0].detail == "daily limit"


def test_withdrawal_beyond_funds_is_audited():
    bank = Bank()
    bank.open_account("S1", "savings", "50")
    with pytest.raises(InsufficientFundsError):
        bank.withdraw("S1", "60")
    assert bank.account("S1").balance == Decimal("50.00")
    assert bank.audit.rejected()[0].detail == "insufficient funds"


def test_bank_transfer_moves_funds_and_audits():
    bank = Bank()
    bank.open_account("C1", "checking", "100")
    bank.open_account("S1", "savings")
    bank.transfer("C1", "S1", "40", "savings")
    assert bank.account("C1").balance == Decimal("60.00")
    assert bank.account("S1").balance == Decimal("40.00")
    assert bank.audit.for_account("C1")[-1].detail == "to S1"
    assert bank.total_balance() == Decimal("100.00")


def test_rejected_bank_transfer_is_audited():
    bank = Bank()
    bank.open_account("S1", "savings", "10")
    bank.open_account("S2", "savings")
    with pytest.raises(InsufficientFundsError):
        bank.transfer("S1", "S2", "25")
    assert bank.account("S2").history == []
    assert bank.audit.rejected()[-1].action == "transfer"


def test_month_end_charges_fees_by_product():
    bank = Bank()
    bank.open_account("C1", "checking", "100")
    bank.open_account("C2", "checking", "1500")
    results = bank.run_month_end(JAN_31)
    assert results["C1"].fee == Decimal("2.50")
    assert results["C2"].fee == Decimal("0.00")
    assert results["C1"].interest == Decimal("0.00")
    assert bank.account("C1").balance == Decimal("97.50")
    assert bank.account("C1").history[-1].posted_on == JAN_31


def test_month_end_reports_interest_for_savings():
    bank = Bank()
    bank.open_account("S1", "savings", "1000")
    results = bank.run_month_end(JAN_31)
    assert results["S1"] == MonthEndResult(Decimal("0.00"), Decimal("2.00"))
    assert bank.account("S1").history[-1].kind == "interest"


def test_statement_totals_and_balances():
    account = make_account()
    account.deposit("100", posted_on=date(2023, 12, 20))
    account.deposit("50", "salary", JAN_1)
    account.withdraw("30", "rent", JAN_15)
    account.record("fee", Decimal("2.50"), "Monthly fee", JAN_31)
    account.deposit("5", posted_on=FEB_1)
    statement = build_statement(account, JAN_1, JAN_31)
    assert statement.opening_balance == Decimal("100.00")
    assert statement.total_credits == Decimal("50.00")
    assert statement.total_debits == Decimal("32.50")
    assert statement.closing_balance == Decimal("117.50")
    assert statement.closing_balance == account.balance_at(JAN_31)
    assert len(statement.transactions) == 3


def test_statement_interest_earned():
    account = make_account()
    account.record("interest", Decimal("1.25"), "Monthly interest", JAN_31)
    assert build_statement(account, JAN_1, JAN_31).interest_earned == Decimal("1.25")


def test_statement_rejects_reversed_period():
    with pytest.raises(ValueError):
        build_statement(make_account(), JAN_31, JAN_1)
    with pytest.raises(ValueError):
        average_daily_balance(make_account(), JAN_31, JAN_1)


def test_average_daily_balance():
    account = make_account()
    account.deposit("100", posted_on=JAN_1)
    account.deposit("300", posted_on=date(2024, 1, 3))
    assert average_daily_balance(account, JAN_1, date(2024, 1, 4)) == Decimal("250.00")
    assert average_daily_balance(account, JAN_1, date(2024, 1, 3)) == to_money("200")


def test_export_csv():
    account = make_account()
    account.deposit("1500", "salary, January", JAN_1)
    account.withdraw("20", "cash", JAN_15)
    text = export_csv(build_statement(account, JAN_1, JAN_31))
    assert text.splitlines() == [
        "date,kind,reference,amount,balance",
        '2024-01-01,deposit,"salary, January",1500.00,1500.00',
        "2024-01-15,withdrawal,cash,-20.00,1480.00",
    ]


def test_add_months_clamps_to_month_end():
    assert add_months(JAN_31, 1) == date(2024, 2, 29)
    assert add_months(date(2023, 12, 15), 1) == JAN_15
    assert add_months(JAN_31, 13) == date(2025, 2, 28)


def test_scheduled_payment_runs_and_advances():
    bank = Bank()
    bank.open_account("C1", "checking", "1000")
    bank.open_account("S1", "savings")
    scheduler = PaymentScheduler(bank)
    payment = scheduler.schedule("C1", "S1", "100", JAN_31)
    assert scheduler.run(JAN_15) == []
    outcomes = scheduler.run(JAN_31)
    assert [outcome.succeeded for outcome in outcomes] == [True]
    assert payment.next_due == date(2024, 2, 29)
    assert bank.account("S1").balance == Decimal("100.00")


def test_weekly_payment_is_paid_once_per_run():
    bank = Bank()
    bank.open_account("C1", "checking", "1000")
    bank.open_account("S1", "savings")
    scheduler = PaymentScheduler(bank)
    payment = scheduler.schedule("C1", "S1", "10", JAN_1, Frequency.WEEKLY)
    scheduler.run(JAN_31)
    assert payment.next_due == date(2024, 1, 8)
    assert bank.account("S1").balance == Decimal("10.00")


def test_failed_payment_is_retried_then_suspended():
    bank = Bank()
    bank.open_account("S1", "savings", "5")
    bank.open_account("S2", "savings")
    scheduler = PaymentScheduler(bank, max_failures=2)
    payment = scheduler.schedule("S1", "S2", "50", JAN_1)
    first = scheduler.run(JAN_1)
    assert [(outcome.succeeded, outcome.detail) for outcome in first] == [
        (False, "insufficient funds")
    ]
    assert payment.active and payment.next_due == JAN_1 and payment.failures == 1
    scheduler.run(JAN_15)
    assert not payment.active
    assert scheduler.due(FEB_1) == []
    assert bank.account("S2").history == []


def test_schedule_validation_and_cancel():
    bank = Bank()
    bank.open_account("C1", "checking")
    bank.open_account("S1", "savings")
    scheduler = PaymentScheduler(bank)
    with pytest.raises(ValueError):
        scheduler.schedule("C1", "C1", "10", JAN_1)
    with pytest.raises(ValueError):
        scheduler.schedule("C1", "S1", "0", JAN_1)
    with pytest.raises(AccountNotFoundError):
        scheduler.schedule("C1", "X", "10", JAN_1)
    with pytest.raises(ValueError):
        PaymentScheduler(bank, max_failures=0)
    payment = scheduler.schedule("C1", "S1", "10", JAN_1)
    scheduler.cancel(payment.payment_id)
    assert scheduler.run(JAN_31) == []
