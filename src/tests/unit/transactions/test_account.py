"""Funding-account aggregate business-rule tests."""

from datetime import datetime
from uuid import uuid4

import pytest

from apps.transactions.domain.entities import Account
from apps.transactions.domain.exceptions import InvalidAccountType
from apps.transactions.domain.value_objects import AccountId, AccountType

from .fakes import FIXED_NOW

pytestmark = pytest.mark.unit


def _new_account(**overrides: object) -> Account:
    values: dict[str, object] = {
        "user_id": uuid4(),
        "name": "  Main   Card ",
        "account_type": AccountType.CREDIT_CARD,
        "now": FIXED_NOW,
    }
    values.update(overrides)
    return Account.create(**values)  # type: ignore[arg-type]


def test_account_starts_active_unidentified_and_normalized() -> None:
    account = _new_account()

    assert account.id is None
    assert account.name == "Main Card"
    assert account.account_type is AccountType.CREDIT_CARD
    assert account.is_active is True
    assert account.created_at == FIXED_NOW
    assert account.updated_at == FIXED_NOW


def test_account_deactivate_stops_offering_it_as_a_funding_source() -> None:
    account = _new_account()
    later = datetime(2025, 1, 16, tzinfo=FIXED_NOW.tzinfo)

    account.deactivate(now=later)

    assert account.is_active is False
    assert account.updated_at == later
    assert account.created_at == FIXED_NOW


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_account_rejects_empty_or_oversized_names(name: str) -> None:
    with pytest.raises(ValueError):
        _new_account(name=name)


def test_account_rejects_an_unsupported_type_enum() -> None:
    with pytest.raises(InvalidAccountType):
        _new_account(account_type="credit_card")


def test_account_requires_a_uuid_owner() -> None:
    with pytest.raises(TypeError, match="UUID"):
        _new_account(user_id="not-a-uuid")


def test_account_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _new_account(now=datetime(2025, 1, 15, 12))


def test_account_identity_wraps_uuid_and_rejects_other_values() -> None:
    account_id = uuid4()

    assert str(AccountId(account_id)) == str(account_id)
    with pytest.raises(TypeError):
        AccountId(str(account_id))  # type: ignore[arg-type]


def test_account_types_have_stable_api_values() -> None:
    assert [item.value for item in AccountType] == [
        "credit_card",
        "debit",
        "cash",
        "savings",
    ]
    assert AccountType.CREDIT_CARD.label == "Credit card"
