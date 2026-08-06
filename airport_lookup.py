"""Deterministic IATA airport code -> city name resolution.

Uses the offline `airportsdata` package — a static, bundled dataset, no
network call and no LLM involved. Airport codes never need to be
"interpreted," so this stays fully deterministic.
"""
import airportsdata

_AIRPORTS = airportsdata.load("IATA")

# Cities with multiple airports where a naive first-match lookup would
# likely pick the wrong one — extend this as you hit more mismatches.
_CITY_TO_IATA_OVERRIDES = {
    "new york": "JFK",
    "london": "LHR",
    "paris": "CDG",
    "tokyo": "HND",
    "chicago": "ORD",
    "moscow": "SVO",
    "washington": "IAD",
    "milan": "MXP",
    "shanghai": "PVG",
    "beijing": "PEK",
    "bangkok": "BKK",
    "houston": "IAH",
    "dallas": "DFW",
    "sao paulo": "GRU",
    "rio de janeiro": "GIG",
}

# Naive city -> first-matching-airport index, built once at import time.
# Not guaranteed to be the primary/largest airport for a city — only the
# overrides above are curated. Good enough for common single-airport
# cities; expand overrides as ambiguous cities come up in testing.
_CITY_INDEX: dict[str, str] = {}
for _code, _info in _AIRPORTS.items():
    _city = (_info.get("city") or "").strip().lower()
    if _city and _city not in _CITY_INDEX:
        _CITY_INDEX[_city] = _code


def resolve_city(iata_code: str) -> str:
    """Resolve an IATA airport code to a "City, Country" string suitable
    for weather/hotel lookups (which expect a place name, not a code).
    Falls back to the raw input if it's not a known code (e.g. the input
    was already a city name — passed through unchanged).
    """
    info = _AIRPORTS.get(iata_code.upper())
    if not info:
        return iata_code
    city = info.get("city") or iata_code
    country = info.get("country")
    return f"{city}, {country}" if country else city


def resolve_iata(location: str) -> str:
    """Resolve a city name OR an IATA code to an IATA code, for flight
    search. If the input is already a known code, it's returned unchanged.
    Otherwise looks up by city name (checking overrides for multi-airport
    cities first). Returns the input unchanged if no match is found, so
    the flight API surfaces a clear error rather than us guessing wrong.
    """
    code = location.strip().upper()
    if code in _AIRPORTS:
        return code

    city_key = location.strip().lower()
    if city_key in _CITY_TO_IATA_OVERRIDES:
        return _CITY_TO_IATA_OVERRIDES[city_key]
    if city_key in _CITY_INDEX:
        return _CITY_INDEX[city_key]

    return location