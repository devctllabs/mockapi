from __future__ import annotations

import re

COUNTER_ID_PATTERNS = (
    re.compile(r"\bnewIdAllocator\b", re.IGNORECASE),
    re.compile(r"\bidCounters\b", re.IGNORECASE),
    re.compile(
        r"\b(?:generated|allocated|counter(?:-based)?|sequential|prefixed?|prefix)\s+"
        r"(?:[A-Za-z0-9_-]+\s+){0,4}ids?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bids?\s+(?:[A-Za-z0-9_-]+\s+){0,4}"
        r"(?:generated|allocated|counter(?:-based)?|sequential|prefixed?|prefix)\b",
        re.IGNORECASE,
    ),
)

SLUG_ID_PATTERNS = (
    re.compile(r"\bslug[- ]style\s+(?:generated\s+)?ids?\b", re.IGNORECASE),
    re.compile(r"\bslug(?:ified)?\s+(?:generated\s+)?ids?\b", re.IGNORECASE),
    re.compile(r"\b(?:ids?|identifiers?)\s+(?:from|derived from)\s+(?:the\s+)?(?:name|title|slug)\b", re.IGNORECASE),
    re.compile(r"\bname-derived\s+ids?\b", re.IGNORECASE),
)

SLUG_ID_OPT_IN_PATTERNS = (
    re.compile(
        r"\b(?:explicit(?:ly)?|confirmed|intentional(?:ly)?|required|must|requires)\b"
        r".{0,120}\b(?:slug[- ]style|slugified|name-derived|ids?\s+from\s+(?:name|title|slug))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:slug[- ]style|slugified|name-derived|ids?\s+from\s+(?:name|title|slug))\b"
        r".{0,120}\b(?:explicit(?:ly)?|confirmed|intentional(?:ly)?|required|must|requires)\b",
        re.IGNORECASE,
    ),
)


def mentions_counter_id_policy(text: str) -> bool:
    return any(pattern.search(text) for pattern in COUNTER_ID_PATTERNS)


def mentions_slug_id_policy(text: str) -> bool:
    return any(pattern.search(text) for pattern in SLUG_ID_PATTERNS)


def has_explicit_slug_id_opt_in(text: str) -> bool:
    return mentions_slug_id_policy(text) and any(pattern.search(text) for pattern in SLUG_ID_OPT_IN_PATTERNS)
