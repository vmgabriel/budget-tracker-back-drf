"""Profile value-object tests."""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from apps.profile.domain.exceptions import (
    BioTooLong,
    InvalidCurrency,
    InvalidLanguage,
    InvalidTimezone,
)
from apps.profile.domain.value_objects import (
    DATE_FORMAT_CHOICES,
    AvatarUrl,
    Bio,
    Currency,
    DateFormat,
    FullName,
    Language,
    ProfileId,
    Timezone,
    UserId,
)

pytestmark = pytest.mark.unit


def test_profile_id_and_user_id_wrap_uuids_and_reject_other_values() -> None:
    value = uuid4()

    assert str(ProfileId(value)) == str(value)
    assert str(UserId(value)) == str(value)
    with pytest.raises(TypeError):
        ProfileId(str(value))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        UserId(str(value))  # type: ignore[arg-type]


def test_full_name_normalizes_whitespace_and_composes_display() -> None:
    name = FullName("  Mary   Jane ", " Watson ")

    assert name.first_name == "Mary Jane"
    assert name.last_name == "Watson"
    assert name.display == "Mary Jane Watson"
    with pytest.raises(FrozenInstanceError):
        name.first_name = "Changed"  # type: ignore[misc]


def test_full_name_allows_a_single_part() -> None:
    assert FullName("Madonna", "").display == "Madonna"
    assert FullName("", " Watson ").display == "Watson"


@pytest.mark.parametrize("first,last", [("", ""), ("  ", "   ")])
def test_full_name_rejects_two_blank_parts(first: str, last: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        FullName(first, last)


@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_full_name_rejects_parts_over_100_characters(field: str) -> None:
    parts = {"first_name": "Valid", "last_name": "Name"}
    parts[field] = "x" * 101
    with pytest.raises(ValueError, match="100 characters"):
        FullName(**parts)


def test_timezone_accepts_iana_names_and_strips_whitespace() -> None:
    assert Timezone("UTC").value == "UTC"
    assert Timezone(" America/Bogota ").value == "America/Bogota"


@pytest.mark.parametrize(
    "value", ["Fake/Zone", "america/bogota", "UTC+1", "Bogota", ""]
)
def test_timezone_rejects_unknown_or_misspelled_names(value: str) -> None:
    with pytest.raises(InvalidTimezone, match="IANA timezone"):
        Timezone(value)


def test_language_normalizes_to_lowercase_iso_639_1() -> None:
    assert Language("PT").value == "pt"
    assert Language(" en ").value == "en"
    assert Language("es").value == "es"


@pytest.mark.parametrize("value", ["xx", "eng", "e", "en-US", "12"])
def test_language_rejects_non_iso_639_1_codes(value: str) -> None:
    with pytest.raises(InvalidLanguage, match="ISO 639-1"):
        Language(value)


def test_currency_normalizes_to_uppercase_iso_4217() -> None:
    assert Currency("cop").value == "COP"
    assert Currency(" eur ").value == "EUR"
    assert Currency("USD").value == "USD"


@pytest.mark.parametrize("value", ["XYZ", "BTC", "US", "USDD", "12"])
def test_currency_rejects_non_iso_4217_codes(value: str) -> None:
    with pytest.raises(InvalidCurrency, match="ISO 4217"):
        Currency(value)


def test_date_format_has_stable_api_values_and_matching_choices() -> None:
    assert [item.value for item in DateFormat] == [
        "YYYY-MM-DD",
        "DD/MM/YYYY",
        "MM/DD/YYYY",
    ]
    assert tuple(value for value, _label in DATE_FORMAT_CHOICES) == tuple(
        item.value for item in DateFormat
    )
    with pytest.raises(ValueError):
        DateFormat("31-12-2026")


def test_avatar_url_accepts_http_and_https_urls() -> None:
    assert AvatarUrl("https://cdn.example.com/a.png").value == (
        "https://cdn.example.com/a.png"
    )
    assert AvatarUrl(" http://localhost:8000/media/a.png ").value == (
        "http://localhost:8000/media/a.png"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-url",
        "ftp://example.com/a.png",
        "example.com/a.png",
        "https://exa mple.com/a.png",
        "https://" + "a" * 194,
    ],
)
def test_avatar_url_rejects_malformed_or_oversized_urls(value: str) -> None:
    with pytest.raises(ValueError):
        AvatarUrl(value)


def test_bio_strips_edges_and_preserves_inner_content() -> None:
    bio = Bio("  Hello,\nI track budgets.  ")

    assert bio.value == "Hello,\nI track budgets."
    with pytest.raises(FrozenInstanceError):
        bio.value = "Changed"  # type: ignore[misc]


def test_bio_accepts_exactly_500_characters() -> None:
    assert Bio("x" * 500).value == "x" * 500


def test_bio_rejects_more_than_500_characters() -> None:
    with pytest.raises(BioTooLong, match="500 characters"):
        Bio("x" * 501)


@pytest.mark.parametrize("value", ["", "   "])
def test_bio_rejects_blank_values(value: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        Bio(value)
