from app.services.test_runner import expand_test_ids, parse_pytest_summary


def test_pytest_ids_match_manifest_selectors_on_windows():
    output = (
        "PASSED tests\\test_ledger.py::test_balance\n"
        "FAILED tests\\test_ledger.py::test_transfer[insufficient] - AssertionError\n"
    )

    result = parse_pytest_summary(output)

    assert result.passed == {"tests/test_ledger.py::test_balance"}
    assert result.failed == {"tests/test_ledger.py::test_transfer[insufficient]"}
    assert expand_test_ids(("tests/test_ledger.py::test_transfer",), result.all_tests) == {
        "tests/test_ledger.py::test_transfer[insufficient]"
    }
