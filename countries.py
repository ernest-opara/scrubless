"""ISO-3166-1 alpha-2 → (display name, flag emoji) lookup.

Kept here so admin.py can render geographic stats without pulling in a
heavier dependency like `pycountry`. Covers the ~100 countries we're
likely to ever see traffic from; anything missing falls back to the
ISO code itself so the panel never breaks on an unknown CDN value.
"""

# alpha-2 → (name, flag-emoji). Flags are two regional-indicator codepoints
# (offset 0x1F1A5 from the ASCII letter), generated at import time.
_NAMES = {
    "US": "United States", "GB": "United Kingdom", "CA": "Canada",
    "AU": "Australia", "NZ": "New Zealand", "IE": "Ireland",
    "DE": "Germany", "FR": "France", "ES": "Spain", "IT": "Italy",
    "NL": "Netherlands", "BE": "Belgium", "PT": "Portugal", "CH": "Switzerland",
    "AT": "Austria", "SE": "Sweden", "NO": "Norway", "DK": "Denmark",
    "FI": "Finland", "IS": "Iceland", "PL": "Poland", "CZ": "Czechia",
    "SK": "Slovakia", "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria",
    "GR": "Greece", "HR": "Croatia", "SI": "Slovenia", "EE": "Estonia",
    "LV": "Latvia", "LT": "Lithuania", "UA": "Ukraine", "RU": "Russia",
    "BY": "Belarus", "MD": "Moldova", "RS": "Serbia", "BA": "Bosnia",
    "MK": "North Macedonia", "AL": "Albania", "ME": "Montenegro",
    "TR": "Turkey", "CY": "Cyprus", "MT": "Malta", "LU": "Luxembourg",
    "MX": "Mexico", "BR": "Brazil", "AR": "Argentina", "CL": "Chile",
    "CO": "Colombia", "PE": "Peru", "VE": "Venezuela", "EC": "Ecuador",
    "UY": "Uruguay", "PY": "Paraguay", "BO": "Bolivia", "CR": "Costa Rica",
    "PA": "Panama", "DO": "Dominican Republic", "GT": "Guatemala",
    "HN": "Honduras", "SV": "El Salvador", "NI": "Nicaragua", "CU": "Cuba",
    "JM": "Jamaica", "PR": "Puerto Rico", "HT": "Haiti", "TT": "Trinidad",
    "JP": "Japan", "CN": "China", "KR": "South Korea", "TW": "Taiwan",
    "HK": "Hong Kong", "SG": "Singapore", "MY": "Malaysia", "TH": "Thailand",
    "VN": "Vietnam", "PH": "Philippines", "ID": "Indonesia", "IN": "India",
    "PK": "Pakistan", "BD": "Bangladesh", "LK": "Sri Lanka", "NP": "Nepal",
    "MM": "Myanmar", "KH": "Cambodia", "LA": "Laos", "MN": "Mongolia",
    "KZ": "Kazakhstan", "UZ": "Uzbekistan", "AF": "Afghanistan",
    "IR": "Iran", "IQ": "Iraq", "SA": "Saudi Arabia", "AE": "UAE",
    "IL": "Israel", "JO": "Jordan", "LB": "Lebanon", "SY": "Syria",
    "QA": "Qatar", "KW": "Kuwait", "OM": "Oman", "BH": "Bahrain", "YE": "Yemen",
    "EG": "Egypt", "MA": "Morocco", "TN": "Tunisia", "DZ": "Algeria",
    "LY": "Libya", "SD": "Sudan", "ET": "Ethiopia", "KE": "Kenya",
    "TZ": "Tanzania", "UG": "Uganda", "RW": "Rwanda", "NG": "Nigeria",
    "GH": "Ghana", "CI": "Ivory Coast", "SN": "Senegal", "CM": "Cameroon",
    "ZA": "South Africa", "ZW": "Zimbabwe", "ZM": "Zambia", "AO": "Angola",
    "MZ": "Mozambique", "MG": "Madagascar", "BJ": "Benin", "BF": "Burkina Faso",
    "ML": "Mali", "GN": "Guinea", "LR": "Liberia", "SL": "Sierra Leone",
    "TG": "Togo", "NE": "Niger", "TD": "Chad", "SS": "South Sudan",
    "CD": "DR Congo", "CG": "Congo", "GA": "Gabon", "FJ": "Fiji",
    "PG": "Papua New Guinea", "GE": "Georgia", "AM": "Armenia", "AZ": "Azerbaijan",
}


def _flag(code):
    """Convert an ISO-2 country code to its flag emoji."""
    if not code or len(code) != 2:
        return ""
    a = ord(code[0].upper())
    b = ord(code[1].upper())
    if not (ord("A") <= a <= ord("Z") and ord("A") <= b <= ord("Z")):
        return ""
    return chr(0x1F1E6 + (a - ord("A"))) + chr(0x1F1E6 + (b - ord("A")))


def country_label(code):
    """{'iso': 'US', 'name': 'United States', 'flag': '🇺🇸'} for any input."""
    code = (code or "").upper()
    return {
        "iso": code or "??",
        "name": _NAMES.get(code, code or "Unknown"),
        "flag": _flag(code),
    }
