from decimal import Decimal

import pytest
from banking import (
    Account,
    InsufficientFundsError,
    apply_interest,
    charge_monthly_fee,
    format_money,
    percentage_of,
    statement_lines,
    to_money,
    transfer,
)


def make_account(account_id: str, overdraft_limit: str = "0") -> Account:
    return Account(account_id, overdraft_limit, history=[])


def test_to_money_rounds_to_cents():
    assert to_money("12.3") == Decimal("12.30")
    assert to_money(5) == Decimal("5.00")


def test_to_money_rounds_halves_away_from_zero():
    assert to_money("0.125") == Decimal("0.13")
    assert to_money("2.665") == Decimal("2.67")
    assert to_money("-0.125") == Decimal("-0.13")


def test_to_money_rejects_floats_and_garbage():
    with pytest.raises(TypeError):
        to_money(1.5)
    with pytest.raises(ValueError):
        to_money("abc")


def test_percentage_of():
    assert percentage_of(Decimal("200.00"), Decimal("2.5")) == Decimal("5.00")


def test_format_money():
    assert format_money(Decimal("-1234.5")) == "-1,234.50"


def test_deposit_and_withdraw():
    account = make_account("A")
    account.deposit("100")
    account.withdraw("30.25")
    assert account.balance == Decimal("69.75")


def test_withdraw_beyond_available_funds_is_rejected():
    account = make_account("A")
    account.deposit("10")
    with pytest.raises(InsufficientFundsError):
        account.withdraw("10.01")
    assert account.balance == Decimal("10.00")
    assert len(account.history) == 1


def test_overdraft_allows_negative_balance():
    account = make_account("A", overdraft_limit="50")
    account.withdraw("40")
    assert account.balance == Decimal("-40.00")


def test_non_positive_amounts_are_rejected():
    with pytest.raises(ValueError):
        make_account("A").deposit("0")


def test_new_accounts_do_not_share_history():
    first = Account("first")
    first.deposit("10")
    second = Account("second")
    assert second.history == []
    assert second.balance == Decimal("0.00")


def test_transfer_moves_funds():
    source, target = make_account("S"), make_account("T")
    source.deposit("100")
    transfer(source, target, "60", "rent")
    assert source.balance == Decimal("40.00")
    assert target.balance == Decimal("60.00")


def test_transfer_to_same_account_is_rejected():
    account = make_account("A")
    with pytest.raises(ValueError):
        transfer(account, account, "1")


def test_failed_transfer_leaves_both_accounts_unchanged():
    source, target = make_account("S"), make_account("T")
    source.deposit("50")
    with pytest.raises(InsufficientFundsError):
        transfer(source, target, "80")
    assert source.balance == Decimal("50.00")
    assert len(source.history) == 1
    assert target.history == []


def test_monthly_fee_is_charged_below_threshold():
    account = make_account("A")
    account.deposit("999.99")
    assert charge_monthly_fee(account) == Decimal("2.50")
    assert account.balance == Decimal("997.49")


def test_monthly_fee_is_waived_at_threshold():
    account = make_account("A")
    account.deposit("1000")
    assert charge_monthly_fee(account) == Decimal("0.00")
    assert len(account.history) == 1


def test_interest_is_not_paid_on_empty_accounts():
    account = make_account("A")
    assert apply_interest(account, "12") == Decimal("0.00")
    assert account.history == []


def test_interest_amount():
    account = make_account("A")
    account.deposit("1000")
    assert apply_interest(account, "5") == Decimal("4.17")


def test_interest_is_credited_to_the_balance():
    account = make_account("A")
    account.deposit("1200")
    apply_interest(account, "12")
    assert account.balance == Decimal("1212.00")


def test_statement_shows_running_balance():
    account = make_account("A")
    account.deposit("100")
    account.withdraw("25")
    lines = statement_lines(account)
    assert lines[0].split() == ["deposit", "100.00", "100.00"]
    assert lines[1].split() == ["withdrawal", "-25.00", "75.00"]
