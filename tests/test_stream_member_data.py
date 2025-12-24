import pytest

from stream_member_data import parse_row


def test_parse_row_valid_payload():
    row = {
        "memberId": "A0",
        "lastTransactionUtcTs": "2019-01-04 17:25:28",
        "lastTransactionType": "gift",
        "lastTransactionPointsBought": "500",
        "lastTransactionRevenueUSD": "2.5",
    }
    payload = parse_row(row)
    assert payload["memberId"] == "A0"
    assert payload["lastTransactionType"] == "GIFT"
    assert payload["lastTransactionRevenueUsd"] == 2.5
    assert payload["lastTransactionUtcTs"].endswith("+00:00")


def test_parse_row_missing_required_fields_raises():
    row = {
        "memberId": "FB608F11",
        "lastTransactionUtcTs": "",
        "lastTransactionType": "",
        "lastTransactionPointsBought": "",
        "lastTransactionRevenueUSD": "",
    }
    with pytest.raises(ValueError):
        parse_row(row)
