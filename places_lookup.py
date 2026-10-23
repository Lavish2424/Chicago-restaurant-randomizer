"""
Google Places (New) text search, mapped onto the fields the Chicago Eats app stores.

No Streamlit imports here, so this file is easy to test on its own.
Docs: https://developers.google.com/maps/documentation/places/web-service/text-search
"""
import requests

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
CHICAGO_CENTER = (41.8781, -87.6298)

# Pro-tier fields (names, address, location, types, status).
_BASE_FIELDS = [
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.primaryType",
    "places.types",
    "places.businessStatus",
]
# priceLevel is billed under the Enterprise SKU (smaller free monthly cap than Pro).
_PRICE_FIELD = "places.priceLevel"

PRICE_MAP = {
    "PRICE_LEVEL_FREE": "$",
    "PRICE_LEVEL_INEXPENSIVE": "$",
    "PRICE_LEVEL_MODERATE": "$$",
    "PRICE_LEVEL_EXPENSIVE": "$$$",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
}

# Google place type -> one of the app's CUISINES labels.
CUISINE_BY_TYPE = {
    "italian_restaurant": "Italian",
    "pizza_restaurant": "Italian",
    "mexican_restaurant": "Mexican",
    "chinese_restaurant": "Chinese",
    "japanese_restaurant": "Japanese",
    "sushi_restaurant": "Japanese",
    "ramen_restaurant": "Japanese",
    "thai_restaurant": "Thai",
    "indian_restaurant": "Indian",
    "french_restaurant": "French",
    "spanish_restaurant": "Spanish",
    "greek_restaurant": "Mediterranean",
    "mediterranean_restaurant": "Mediterranean",
    "middle_eastern_restaurant": "Mediterranean",
    "lebanese_restaurant": "Mediterranean",
    "turkish_restaurant": "Mediterranean",
    "seafood_restaurant": "Seafood",
    "steak_house": "Steakhouse",
    "american_restaurant": "American",
    "hamburger_restaurant": "American",
    "barbecue_restaurant": "American",
    "brunch_restaurant": "American",
    "breakfast_restaurant": "American",
    "diner": "American",
    "asian_restaurant": "Asian",
    "korean_restaurant": "Asian",
    "vietnamese_restaurant": "Asian",
    "indonesian_restaurant": "Asian",
    "cocktail_bar": "Cocktails",
    "wine_bar": "Cocktails",
    "lounge_bar": "Cocktails",
    "bar": "Cocktails",
    "pub": "Cocktails",
}

BAR_TYPES = {
    "bar", "cocktail_bar", "wine_bar", "lounge_bar", "pub", "irish_pub",
    "brewery", "brewpub", "night_club",
}


class PlacesError(Exception):
    """Raised with a human-readable message when a lookup fails."""


def _is_restaurantish(place_type):
    return place_type.endswith("restaurant") or place_type in {"steak_house", "diner"}


def guess_cuisine(types):
    """First matching cuisine label for a list of Google types (primary type first)."""
    for t in types:
        if t in CUISINE_BY_TYPE:
            return CUISINE_BY_TYPE[t]
    return None


def guess_type(primary_type, types):
    """'cocktail_bar' or 'restaurant' (the two values the app stores)."""
    if primary_type in BAR_TYPES:
        return "cocktail_bar"
    if primary_type and _is_restaurantish(primary_type):
        return "restaurant"
    has_bar = any(t in BAR_TYPES for t in types)
    has_restaurant = any(_is_restaurantish(t) for t in types)
    return "cocktail_bar" if has_bar and not has_restaurant else "restaurant"


def parse_place(p):
    """Turn one raw Places API result into the app's field names."""
    primary = p.get("primaryType") or ""
    types = [primary] + [t for t in p.get("types", []) if t != primary]
    types = [t for t in types if t]

    place_type = guess_type(primary, types)
    cuisine = guess_cuisine(types) or ("Cocktails" if place_type == "cocktail_bar" else "Other")

    address = (p.get("formattedAddress") or "").strip()
    if address.endswith(", USA"):
        address = address[: -len(", USA")]

    loc = p.get("location") or {}
    return {
        "place_id": p.get("id"),
        "name": (p.get("displayName") or {}).get("text", "").strip(),
        "address": address,
        "latitude": loc.get("latitude"),
        "longitude": loc.get("longitude"),
        "cuisine": cuisine,
        "type": place_type,
        "price": PRICE_MAP.get(p.get("priceLevel")),  # None when Google has no price info
        "closed": p.get("businessStatus") == "CLOSED_PERMANENTLY",
    }


def _error_message(resp):
    try:
        detail = resp.json().get("error", {}).get("message", "")
    except ValueError:
        detail = ""
    if resp.status_code in (400, 403):
        return (
            "Google rejected the request - check that the Places API (New) is enabled, "
            f"billing is attached, and the key is valid. {detail}".strip()
        )
    if resp.status_code == 429:
        return "Google says the quota is used up for now. Try again later or fill the form by hand."
    return f"Place search failed ({resp.status_code}). {detail}".strip()


def search_places(query, api_key, center=CHICAGO_CENTER, radius_m=50000.0,
                  max_results=5, include_price=True, timeout=10):
    """Search by free text ('Au Cheval Fulton Market'). Returns a list of parsed places."""
    query = (query or "").strip()
    if not query:
        return []
    fields = _BASE_FIELDS + ([_PRICE_FIELD] if include_price else [])
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(fields),
    }
    body = {
        "textQuery": query,
        "maxResultCount": max_results,
        "regionCode": "US",
        "locationBias": {
            "circle": {
                "center": {"latitude": center[0], "longitude": center[1]},
                "radius": radius_m,
            }
        },
    }
    try:
        resp = requests.post(SEARCH_URL, json=body, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise PlacesError(f"Couldn't reach Google Places: {e}") from e
    if resp.status_code != 200:
        raise PlacesError(_error_message(resp))
    return [parse_place(p) for p in resp.json().get("places", [])]
