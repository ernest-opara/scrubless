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


# ISO-3166-1 alpha-2 → list of <path id="…"> attributes in scrubby/world.svg
# (the Wikipedia "World map - low resolution" SVG, which IDs paths by lowercase
# English country names plus separate IDs per island). Multi-island states
# need every island to receive the heatmap tint, hence lists. Anything not
# listed here just isn't shaded on the map — the ranked panel below still
# shows it. Intentional gaps: tiny city-states (LU, MC, SG, MT) aren't
# drawn as distinct paths in the low-res source.
ISO_TO_SVG_IDS = {
    # North America
    "US": ["usa", "alaska", "alaska-westcopy", "hawaii", "kahului", "kauai", "oahu",
           "st. lawrence island", "st. lawrence island west", "unalaska", "unalaska west",
           "umnak", "umnak west", "adak", "adak west", "amchitka", "amchitka west",
           "attu", "attu west", "another aleutian west"],
    "CA": ["canada", "baffin", "ellesmere", "victoria", "banks", "devon", "southhampton",
           "bylot", "axel heiberg", "prince of wales", "prince patrick", "mackenzie king",
           "amund ringnes", "ellef ringnes", "king christian", "cornwallis", "bathurst",
           "newfoundland", "haida gwaii", "vancouver", "melville", "prince george",
           "salisbury", "milne", "king george", "prescott"],
    "MX": ["mexico"],
    "GT": ["guatemala"], "BZ": ["belize"], "HN": ["honduras"], "SV": ["el salvador"],
    "NI": ["nicaragua"], "CR": ["costa rica"], "PA": ["panama"], "CU": ["cuba"],
    "JM": ["jamaica"], "HT": ["haiti"], "DO": ["domincan republic"],  # note SVG typo
    "PR": ["puerto rico"], "BS": ["andros", "eleuthera", "grand bahama", "inagua", "bimini"],
    "DM": ["dominica"], "LC": ["st. lucia"], "VC": ["st. vincent"], "GD": ["grenada"],
    "TT": ["trinidad"], "GP": ["guadeloupe"], "MQ": ["martinique"],
    # South America
    "BR": ["brazil"], "AR": ["argentina", "tierra del fuego argentina"],
    "CL": ["chile", "tierra del fuego chile", "chiloe"], "PE": ["peru"], "CO": ["colombia"],
    "VE": ["venezuela"], "EC": ["ecuador", "galapagos"], "BO": ["bolivia"],
    "PY": ["paraguay"], "UY": ["uruguay"], "GY": ["guyana"], "SR": ["suriname"],
    "GF": ["guyane"],
    # Europe
    "GB": ["britain", "ulster"], "IE": ["ireland"], "FR": ["france", "corsica"],
    "DE": ["germany"], "ES": ["spain", "majorca"], "PT": ["portugal", "madeira",
           "sao miguel", "pico", "terceira"], "IT": ["italy", "sardinia", "sicily"],
    "NL": ["netherlands"], "BE": ["belgium"], "CH": ["switzerland"], "AT": ["austria"],
    "SE": ["sweden", "gotland"], "NO": ["norway", "spitsbergen", "edgeoya", "nordaustlandet"],
    "DK": ["denmark", "sjælland", "greenland", "disko"],  # Greenland is DK territory
    "FI": ["finland"], "IS": ["iceland"], "PL": ["poland"], "CZ": ["czech"],
    "SK": ["slovakia"], "HU": ["hungary"], "RO": ["romania"], "BG": ["bulgaria"],
    "GR": ["greece", "crete", "thrace"], "HR": ["croatia"], "SI": ["slovenia"],
    "EE": ["estonia", "saaremaa", "hiumaa"], "LT": ["lithuania"], "LV": ["latvia"],
    "UA": ["ukraine"], "BY": ["belarus"], "MD": ["moldova"], "RS": ["serbia"],
    "BA": ["bosnia"], "MK": ["macedonia"], "AL": ["albania"], "ME": ["montenegro"],
    "CY": ["cyprus"], "FO": [],  # Faroe — not drawn distinctly
    # Russia + Caucasus + Central Asia
    "RU": ["russia", "sakhalin", "novaya zemlya north", "novaya zemlya south",
           "bolshevik", "kotelny", "lyakhovsky", "komsomolets", "novaya sibir",
           "october", "wrangel", "wrangel-w", "urup", "iturup", "paramushir",
           "onekotan", "chukotka", "bering island", "medny", "wilczek", "bell",
           "alexander", "robert"],
    "GE": ["georgia"], "AM": ["armenia"], "AZ": ["azerbaijan"],
    "KZ": ["kazakhstan"], "UZ": ["uzbekistan"], "TM": ["turkmenistan"],
    "KG": ["kirgizstan"], "TJ": ["tajikistan"],
    # Middle East
    "TR": ["turkey"], "IR": ["iran"], "IQ": ["iraq"], "SY": ["syria"], "LB": ["lebanon"],
    "JO": ["jordan"], "IL": ["israel"], "PS": [],  # not distinct path
    "SA": ["saudi"], "YE": ["yemen", "soqotra"], "OM": ["oman"], "AE": ["emirates"],
    "QA": ["qatar"], "KW": ["kuwait"], "AF": ["afghanistan"],
    # South Asia
    "IN": ["india"], "PK": ["pakistan"], "BD": ["bangladesh"], "NP": ["nepal"],
    "BT": ["bhutan"], "LK": ["sri lanka"], "MV": ["maldive", "male", "gan"],
    # East / SE Asia
    "CN": ["china", "hainan"], "JP": ["honshu", "hokkaido", "kyushu", "shikoku"],
    "KR": ["south korea"], "KP": ["north korea"], "TW": ["taiwan"],
    "MN": ["mongolia"], "MM": ["burma"], "TH": ["thailand"], "VN": ["vietnam"],
    "LA": ["laos"], "KH": ["cambodia"], "MY": ["malaysia", "east malaysia"],
    "ID": ["sumatra", "java", "kalimantan", "sulawesi", "irian jaya", "maluku",
           "bali", "flores", "lombok", "sumba", "seram"],
    "TL": ["timor"], "BN": ["brunei"],
    "PH": ["luzon", "mindoro", "palawan", "samar", "cebu", "negros"],
    "PG": ["papua new guinea", "new britain", "new ireland", "bougainville"],
    # Africa
    "EG": ["egypt"], "LY": ["libya"], "TN": ["tunisia"], "DZ": ["algeria"],
    "MA": ["morocco"], "EH": [],  # Western Sahara not distinct
    "SD": ["sudan"], "SS": ["south_sudan"], "ER": ["eritrea"], "ET": ["ethiopia"],
    "DJ": ["djibouti"], "SO": ["somalia"], "KE": ["kenya"], "UG": ["uganda"],
    "TZ": ["tanzania"], "RW": ["rwanda"], "BI": ["burundi"], "CD": ["drc"],
    "CG": ["congo"], "CF": ["centrafrique"], "CM": ["cameroon"], "GA": ["gabon"],
    "GQ": ["equatorial guinea", "bioko"], "ST": ["sao tome", "principe"],
    "NG": ["nigeria"], "BJ": ["benin"], "TG": ["togo"], "GH": ["ghana"],
    "CI": ["ivoire"], "LR": ["liberia"], "SL": ["sierra leone"], "GN": ["guinee"],
    "GW": ["bissau"], "SN": ["senegal", "casamance"], "GM": ["gambia"],
    "MR": ["mauretania"], "ML": ["mali"], "BF": ["burkina"], "NE": ["niger"],
    "TD": ["chad"], "AO": ["angola", "cabinda"], "ZM": ["zambia"], "ZW": ["zimbabwe"],
    "MZ": ["mozambique"], "MW": ["malawi"], "BW": ["botswana"], "NA": ["namibia"],
    "ZA": ["south africa", "lesotho"],  # Lesotho enclave best with ZA visually
    "LS": [], "SZ": ["swaziland"], "MG": ["madagascar"], "MU": ["mauritius"],
    "RE": ["reunion"], "YT": ["mayotte"], "KM": ["grande comore"], "SC": ["mahe", "praslin"],
    "CV": ["santiago", "santo antao", "boa vista"],
    # Oceania
    "AU": ["australia", "tasmania"], "NZ": ["new zealand north island", "new zealand south island"],
    "FJ": ["fiji"], "NC": ["new caledonia"], "VU": ["espiritu santo", "malakula", "efate"],
    "SB": ["choiseul", "santa isabel", "new georgia", "guadalcanal", "malaita", "rennell"],
    "PF": ["tahiti", "raiatea"],
}


def iso_to_svg_ids():
    """Public accessor — returned by the admin stats so the frontend can paint
    the world-map heatmap without bundling this dict in JS."""
    return ISO_TO_SVG_IDS
