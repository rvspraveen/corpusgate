"""Named regex patterns for lightweight PII smoke tests.

These are deliberately simple. They are not a DLP tool: see LIMITATIONS.md.
"""

from __future__ import annotations

PII_PATTERNS: dict[str, str] = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "us_phone": r"(?:\+1[\s.-]?)?\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b",
    "us_ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "card_number": r"\b(?:\d[ -]?){13,16}\b",
    "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}
