"""Redaction of the portal's storage model, shared by diagnostics and logging.

Diagnostics downloads and debug logs both end up attached to public GitHub
issues, so anything that identifies the owner or locates the site has to be
stripped from either of them by the same rules.
"""
from __future__ import annotations

import re
from typing import Any

REDACTED = "**REDACTED**"

# The storage model comes from an undocumented endpoint, so its fields are not
# a known list to check against. Redact by shape instead: anything whose name
# suggests it identifies the owner or locates the site. A settings field slipping
# through is a nuisance; an address reaching a public issue is not.
MODEL_REDACT_HINTS = (
    "mail",
    "phone",
    "mobile",
    "address",
    "owner",
    "name",
    "latitude",
    "longitude",
    "token",
    "user",
    "account",
)

# The coordinate abbreviations have to match a whole word rather than any
# substring: as a bare substring "lat" also blanks out latestVersion and the
# like, which only makes a diagnostics dump harder to read.
MODEL_REDACT_WORD_HINTS = ("lat", "lng", "lon")

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def _words(key: Any) -> set[str]:
    """Split stationLat, station_lat or stationLAT into comparable words."""
    return set(_NON_WORD.split(_CAMEL_BOUNDARY.sub(" ", str(key)).lower()))


def _is_identifying(key: Any) -> bool:
    """Whether a field name looks like it identifies the owner or the site."""
    lowered = str(key).lower()
    if any(hint in lowered for hint in MODEL_REDACT_HINTS):
        return True
    return bool(_words(key) & set(MODEL_REDACT_WORD_HINTS))


def redact_model(value: Any) -> Any:
    """Recursively blank out owner- or site-identifying fields."""
    if isinstance(value, dict):
        return {
            k: (REDACTED if _is_identifying(k) else redact_model(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_model(v) for v in value]
    return value
