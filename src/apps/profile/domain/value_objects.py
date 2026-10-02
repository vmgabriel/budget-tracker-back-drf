"""Immutable value objects for the profile domain."""

import re
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from uuid import UUID
from zoneinfo import available_timezones

from apps.profile.domain.exceptions import (
    BioTooLong,
    InvalidCurrency,
    InvalidLanguage,
    InvalidTimezone,
)

MAX_NAME_PART_LENGTH = 100
MAX_AVATAR_URL_LENGTH = 200
MAX_BIO_LENGTH = 500

_AVATAR_URL_PATTERN = re.compile(r"^https?://[^\s/]+(?:/[^\s]*)?$", re.IGNORECASE)

_ISO_639_1_CODES: frozenset[str] = frozenset(
    {
        "aa",
        "ab",
        "ae",
        "af",
        "ak",
        "am",
        "an",
        "ar",
        "as",
        "av",
        "ay",
        "az",
        "ba",
        "be",
        "bg",
        "bh",
        "bi",
        "bm",
        "bn",
        "bo",
        "br",
        "bs",
        "ca",
        "ce",
        "ch",
        "co",
        "cr",
        "cs",
        "cu",
        "cv",
        "cy",
        "da",
        "de",
        "dv",
        "dz",
        "ee",
        "el",
        "en",
        "eo",
        "es",
        "et",
        "eu",
        "fa",
        "ff",
        "fi",
        "fj",
        "fo",
        "fr",
        "fy",
        "ga",
        "gd",
        "gl",
        "gn",
        "gu",
        "gv",
        "ha",
        "he",
        "hi",
        "ho",
        "hr",
        "ht",
        "hu",
        "hy",
        "hz",
        "ia",
        "id",
        "ie",
        "ig",
        "ii",
        "ik",
        "io",
        "is",
        "it",
        "iu",
        "ja",
        "jv",
        "ka",
        "kg",
        "ki",
        "kj",
        "kk",
        "kl",
        "km",
        "kn",
        "ko",
        "kr",
        "ks",
        "ku",
        "kv",
        "kw",
        "ky",
        "la",
        "lb",
        "lg",
        "li",
        "ln",
        "lo",
        "lt",
        "lu",
        "lv",
        "mg",
        "mh",
        "mi",
        "mk",
        "ml",
        "mn",
        "mr",
        "ms",
        "mt",
        "my",
        "na",
        "nb",
        "nd",
        "ne",
        "ng",
        "nl",
        "nn",
        "no",
        "nr",
        "nv",
        "ny",
        "oc",
        "oj",
        "om",
        "or",
        "os",
        "pa",
        "pi",
        "pl",
        "ps",
        "pt",
        "qu",
        "rm",
        "rn",
        "ro",
        "ru",
        "rw",
        "sa",
        "sc",
        "sd",
        "se",
        "sg",
        "si",
        "sk",
        "sl",
        "sm",
        "sn",
        "so",
        "sq",
        "sr",
        "ss",
        "st",
        "su",
        "sv",
        "sw",
        "ta",
        "te",
        "tg",
        "th",
        "ti",
        "tk",
        "tl",
        "tn",
        "to",
        "tr",
        "ts",
        "tt",
        "tw",
        "ty",
        "ug",
        "uk",
        "ur",
        "uz",
        "ve",
        "vi",
        "vo",
        "wa",
        "wo",
        "xh",
        "yi",
        "yo",
        "za",
        "zh",
        "zu",
    }
)

_ISO_4217_CODES: frozenset[str] = frozenset(
    {
        "AED",
        "AFN",
        "ALL",
        "AMD",
        "ANG",
        "AOA",
        "ARS",
        "AUD",
        "AWG",
        "AZN",
        "BAM",
        "BBD",
        "BDT",
        "BGN",
        "BHD",
        "BIF",
        "BMD",
        "BND",
        "BOB",
        "BOV",
        "BRL",
        "BSD",
        "BTN",
        "BWP",
        "BYN",
        "BZD",
        "CAD",
        "CDF",
        "CHE",
        "CHF",
        "CHW",
        "CLF",
        "CLP",
        "CNY",
        "COP",
        "COU",
        "CRC",
        "CUP",
        "CVE",
        "CZK",
        "DJF",
        "DKK",
        "DOP",
        "DZD",
        "EGP",
        "ERN",
        "ETB",
        "EUR",
        "FJD",
        "FKP",
        "GBP",
        "GEL",
        "GHS",
        "GIP",
        "GMD",
        "GNF",
        "GTQ",
        "GYD",
        "HKD",
        "HNL",
        "HTG",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "IQD",
        "IRR",
        "ISK",
        "JMD",
        "JOD",
        "JPY",
        "KES",
        "KGS",
        "KHR",
        "KMF",
        "KPW",
        "KRW",
        "KWD",
        "KYD",
        "KZT",
        "LAK",
        "LBP",
        "LKR",
        "LRD",
        "LSL",
        "LYD",
        "MAD",
        "MDL",
        "MGA",
        "MKD",
        "MMK",
        "MNT",
        "MOP",
        "MRU",
        "MUR",
        "MVR",
        "MWK",
        "MXN",
        "MXV",
        "MYR",
        "MZN",
        "NAD",
        "NGN",
        "NIO",
        "NOK",
        "NPR",
        "NZD",
        "OMR",
        "PAB",
        "PEN",
        "PGK",
        "PHP",
        "PKR",
        "PLN",
        "PYG",
        "QAR",
        "RON",
        "RSD",
        "RUB",
        "RWF",
        "SAR",
        "SBD",
        "SCR",
        "SDG",
        "SEK",
        "SGD",
        "SHP",
        "SLE",
        "SOS",
        "SRD",
        "SSP",
        "STN",
        "SVC",
        "SYP",
        "SZL",
        "THB",
        "TJS",
        "TMT",
        "TND",
        "TOP",
        "TRY",
        "TTD",
        "TWD",
        "TZS",
        "UAH",
        "UGX",
        "USD",
        "USN",
        "UYI",
        "UYU",
        "UYW",
        "UZS",
        "VED",
        "VES",
        "VND",
        "VUV",
        "WST",
        "XAF",
        "XAG",
        "XAU",
        "XBA",
        "XBB",
        "XBC",
        "XBD",
        "XCD",
        "XCG",
        "XDR",
        "XOF",
        "XPD",
        "XPF",
        "XPT",
        "XSU",
        "XTS",
        "XUA",
        "XXX",
        "YER",
        "ZAR",
        "ZMW",
        "ZWG",
    }
)


@lru_cache(maxsize=1)
def _iana_timezones() -> frozenset[str]:
    """Return the cached set of IANA timezone names known to the system."""
    return frozenset(available_timezones())


class DateFormat(StrEnum):
    """Display formats supported for rendering dates."""

    ISO = "YYYY-MM-DD"
    DAY_FIRST = "DD/MM/YYYY"
    MONTH_FIRST = "MM/DD/YYYY"


DATE_FORMAT_CHOICES: tuple[tuple[str, str], ...] = (
    (DateFormat.ISO.value, "ISO 8601 (YYYY-MM-DD)"),
    (DateFormat.DAY_FIRST.value, "Day first (DD/MM/YYYY)"),
    (DateFormat.MONTH_FIRST.value, "Month first (MM/DD/YYYY)"),
)


@dataclass(frozen=True, slots=True)
class ProfileId:
    """Identity of a persisted profile."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise TypeError("ProfileId must contain a UUID.")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class UserId:
    """Reference to the user that owns a profile; never a foreign key."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise TypeError("UserId must contain a UUID.")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class FullName:
    """A person's name split into normalized given and family name parts."""

    first_name: str
    last_name: str

    def __post_init__(self) -> None:
        first = " ".join(self.first_name.split())
        last = " ".join(self.last_name.split())
        if not first and not last:
            raise ValueError("Full name cannot be empty.")
        if len(first) > MAX_NAME_PART_LENGTH:
            raise ValueError("First name cannot exceed 100 characters.")
        if len(last) > MAX_NAME_PART_LENGTH:
            raise ValueError("Last name cannot exceed 100 characters.")
        object.__setattr__(self, "first_name", first)
        object.__setattr__(self, "last_name", last)

    @property
    def display(self) -> str:
        """Return the combined display name."""
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True, slots=True)
class Timezone:
    """A case-sensitive IANA timezone name such as ``America/Bogota``."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if normalized not in _iana_timezones():
            raise InvalidTimezone("Enter a valid IANA timezone.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class Language:
    """An ISO 639-1 two-letter language code such as ``en`` or ``es``."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if normalized not in _ISO_639_1_CODES:
            raise InvalidLanguage("Enter a valid ISO 639-1 language code.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class Currency:
    """An ISO 4217 three-letter currency code such as ``USD`` or ``COP``."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().upper()
        if normalized not in _ISO_4217_CODES:
            raise InvalidCurrency("Enter a valid ISO 4217 currency code.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class AvatarUrl:
    """An HTTP(S) URL pointing to the user's avatar image."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if len(normalized) > MAX_AVATAR_URL_LENGTH:
            raise ValueError("Avatar URL cannot exceed 200 characters.")
        if not _AVATAR_URL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid avatar URL.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class Bio:
    """A short free-text biography of at most 500 characters."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("Bio cannot be empty.")
        if len(normalized) > MAX_BIO_LENGTH:
            raise BioTooLong("Bio cannot exceed 500 characters.")
        object.__setattr__(self, "value", normalized)
