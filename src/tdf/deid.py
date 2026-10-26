"""De-identification primitives.

All identifiers are replaced with keyed, irreversible pseudonyms (HMAC-SHA256)
so that joins between tables still work while the original serial numbers,
VINs, account identifiers and company names never leave the private
environment. The HMAC key is read from a file outside the repository.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PLACEHOLDER_VALUES = {"", "-", "NAN", "NONE", "NULL", "N/A", "NA"}
PLACEHOLDER_VIN = {"VINNOTYETDETECTED"}
PLACEHOLDER_DRIVER = {"NODRIVERID"}
PLACEHOLDER_TRAILER = {"NOTRAILERGPSID"}

_WS = re.compile(r"\s+")
_NONWORD = re.compile(r"[^0-9a-z ]+")


class Pseudonymizer:
    """Keyed pseudonym generator. Same input + same key -> same output."""

    def __init__(self, key: bytes, digest_chars: int = 10):
        if len(key) < 16:
            raise ValueError("de-identification key must be at least 16 bytes")
        self.key = key
        self.digest_chars = digest_chars

    @classmethod
    def from_file(cls, path: str | os.PathLike) -> "Pseudonymizer":
        raw = Path(path).read_text(encoding="utf-8").strip()
        return cls(bytes.fromhex(raw) if re.fullmatch(r"[0-9a-fA-F]+", raw) else raw.encode())

    @classmethod
    def from_env(cls, var: str = "TDF_DEID_KEY_FILE") -> "Pseudonymizer":
        path = os.environ.get(var)
        if not path:
            raise RuntimeError(f"set {var} to the path of the de-identification key file")
        return cls.from_file(path)

    def _digest(self, namespace: str, value: str) -> str:
        msg = f"{namespace}|{value}".encode("utf-8")
        return hmac.new(self.key, msg, hashlib.sha256).hexdigest()[: self.digest_chars]

    def one(self, namespace: str, prefix: str, value, placeholders: Iterable[str] = ()) -> str | None:
        """Pseudonymize a single value; placeholders and blanks map to None."""
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        s = str(value).strip()
        if s.upper() in PLACEHOLDER_VALUES or s.upper() in set(placeholders):
            return None
        return f"{prefix}{self._digest(namespace, s)}"

    def series(self, s: pd.Series, namespace: str, prefix: str, normalize=None, placeholders: Iterable[str] = ()) -> pd.Series:
        norm = normalize or (lambda x: str(x).strip().upper())
        placeholders = set(p.upper() for p in placeholders)
        cache: dict[str, str | None] = {}
        out = []
        for v in s.tolist():
            if v is None or (isinstance(v, float) and math.isnan(v)):
                out.append(None)
                continue
            n = norm(v)
            if n is None or n.upper() in PLACEHOLDER_VALUES or n.upper() in placeholders:
                out.append(None)
                continue
            if n not in cache:
                cache[n] = f"{prefix}{self._digest(namespace, n)}"
            out.append(cache[n])
        return pd.Series(out, index=s.index, dtype="object")


def normalize_org_name(name) -> str | None:
    """Lower-case, strip a trailing '(DOT)' suffix, collapse whitespace."""
    if name is None or (isinstance(name, float) and math.isnan(name)):
        return None
    s = str(name).strip()
    s = re.sub(r"\(\s*\d{3,9}\s*\)\s*$", "", s)  # '(1234567)' suffix in contract exports
    s = s.lower()
    s = _NONWORD.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s or None


def extract_dot(name) -> str | None:
    """Pull a USDOT number out of 'Org Name (1234567)'."""
    if name is None or (isinstance(name, float) and math.isnan(name)):
        return None
    m = re.search(r"\((\d{3,9})\)\s*$", str(name))
    return m.group(1) if m else None


def clean_dot(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if 3 <= len(digits) <= 9 else None


def coarsen_coordinate(value, step: float = 0.05) -> float | None:
    """Round a coordinate to a coarse grid (0.05 deg ~ 5 km). 0/blank -> None."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(f) or f == 0.0:
        return None
    return round(round(f / step) * step, 4)


_SCRUB_PATTERNS = [
    (re.compile(r"\b\d{15}\b"), "<IMEI>"),
    (re.compile(r"\b\d{19,20}\b"), "<ICCID>"),
    (re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"), "<VIN>"),
    (re.compile(r"\bRT\d{8}\b"), "<SERIAL>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<EMAIL>"),
    (re.compile(r"\(?\b\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"), "<PHONE>"),
    (re.compile(r"-?\d{1,3}\.\d{4,},\s*-?\d{1,3}\.\d{4,}"), "<LATLON>"),
]


def scrub_text(text) -> str | None:
    """Replace identifier-looking substrings in free text with typed tokens."""
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return None
    s = str(text)
    for pat, tok in _SCRUB_PATTERNS:
        s = pat.sub(tok, s)
    return s


_UNIT_SCALE = {"B": 1 / 1_000_000, "KB": 1 / 1_000, "MB": 1.0, "GB": 1_000.0}


def to_number(s: pd.Series) -> pd.Series:
    """Convert strings like '-', '1,234', '45%', '432.5 MB' to floats; non-numeric -> NaN.

    Data-volume suffixes are normalised to megabytes.
    """
    def conv(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return np.nan
        t = str(v).strip().replace(",", "").rstrip("%").strip()
        if t.upper() in PLACEHOLDER_VALUES:
            return np.nan
        m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(B|KB|MB|GB)", t, re.I)
        if m:
            return float(m.group(1)) * _UNIT_SCALE[m.group(2).upper()]
        try:
            return float(t)
        except ValueError:
            return np.nan
    return s.map(conv).astype("float64")


def to_datetime(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.where(~s.astype(str).str.strip().str.upper().isin(PLACEHOLDER_VALUES)), errors="coerce")


US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
}
_STATE_NAMES = {
    "california": "CA", "texas": "TX", "florida": "FL", "new york": "NY", "nevada": "NV", "arizona": "AZ", "washington": "WA", "oregon": "OR", "illinois": "IL", "georgia": "GA", "new jersey": "NJ", "pennsylvania": "PA", "ohio": "OH", "utah": "UT", "colorado": "CO", "north carolina": "NC", "tennessee": "TN", "indiana": "IN", "michigan": "MI", "virginia": "VA", "missouri": "MO", "maryland": "MD", "wisconsin": "WI", "minnesota": "MN", "oklahoma": "OK", "kentucky": "KY", "south carolina": "SC", "alabama": "AL", "louisiana": "LA", "arkansas": "AR", "massachusetts": "MA", "idaho": "ID", "new mexico": "NM", "kansas": "KS", "iowa": "IA", "mississippi": "MS", "nebraska": "NE", "connecticut": "CT", "montana": "MT", "wyoming": "WY", "hawaii": "HI", "alaska": "AK", "maine": "ME", "vermont": "VT", "new hampshire": "NH", "rhode island": "RI", "delaware": "DE", "south dakota": "SD", "north dakota": "ND", "west virginia": "WV",
}


def clean_state(value) -> str | None:
    """Map free-text state spellings to USPS codes; unknown -> None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    s = str(value).strip()
    if not s or s.upper() in PLACEHOLDER_VALUES:
        return None
    u = s.upper()
    if u in US_STATES:
        return u
    low = re.sub(r"[^a-z ]", "", s.lower()).strip()
    return _STATE_NAMES.get(low)


def clean_country(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    low = re.sub(r"[^a-z]", "", str(value).lower())
    if not low or low == "":
        return None
    if low in {"unitedstate", "unitedstates", "usa", "us", "untiedstates", "losangeles"}:
        return "US"
    if low in {"canada", "ca"}:
        return "CA"
    return None
