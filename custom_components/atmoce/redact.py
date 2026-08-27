"""Redaction of the portal's storage model, shared by diagnostics and logging.

Diagnostics downloads and debug logs both end up attached to public GitHub
issues, so anything that identifies the owner or locates the site has to be
stripped from either of them by the same rules.
"""
from __future__ import annotations

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
    "lat",
    "lng",
    "token",
    "user",
    "account",
)


def redact_model(value: Any) -> Any:
    """Recursively blank out owner- or site-identifying fields."""
    if isinstance(value, dict):
        return {
            k: (
                REDACTED
                if any(hint in str(k).lower() for hint in MODEL_REDACT_HINTS)
                else redact_model(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_model(v) for v in value]
    return value
