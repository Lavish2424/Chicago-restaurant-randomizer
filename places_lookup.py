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
    "pizza_restaurant": "Pizza",
    "mexican_restaurant": "Mexican",
    "chinese_restaurant": "Chinese",
    "japanese_restaurant": "Japanese",
    "sushi_restaurant": "Japanese",
    "ramen_restaurant": "Japanese",
    "korean_restaurant": "Korean",
    "vietnamese_restaurant": "Vietnamese",
    "thai_restaurant": "Thai",
    "indian_restaurant": "Indian",
    "french_restaurant": "French",
    "spanish_restaurant": "Spanish",
    "greek_restaurant": "Greek",
    "mediterranean_restaurant": "Mediterranean",
    "middle_eastern_restaurant": "Middle Eastern",
    "lebanese_restaurant": "Middle Eastern",
    "turkish_restaurant": "Middle Eastern",
    "african_restaurant": "African",
    "brazilian_restaurant": "Latin American",
    "seafood_restaurant": "Seafood",
    "steak_house": "Steakhouse",
    "american_restaurant": "American",
    "diner": "American",
    "bar_and_grill": "American",
    "breakfast_restaurant": "American",
    "brunch_restaurant": "American",
    "hamburger_restaurant": "Burgers",
    "barbecue_restaurant": "Barbecue",
    "vegan_restaurant": "Vegetarian & Vegan",
    "vegetarian_restaurant": "Vegetarian & Vegan",
    "sandwich_shop": "Deli & Sandwiches",
    "deli": "Deli & Sandwiches",
    "dessert_shop": "Dessert",
    "dessert_restaurant": "Dessert",
    "ice_cream_shop": "Dessert",
    "candy_store": "Dessert",
    "chocolate_shop": "Dessert",
    "bakery": "Coffee & Bakery",
    "bagel_shop": "Coffee & Bakery",
    "donut_shop": "Coffee & Bakery",
    "cafe": "Coffee & Bakery",
    "coffee_shop": "Coffee & Bakery",
    "tea_house": "Coffee & Bakery",
    "juice_shop": "Coffee & Bakery",
    "asian_restaurant": "Asian",
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
BREAKFAST_TYPES = {"breakfast_restaurant", "brunch_restaurant"}
CAFE_TYPES = {
    "cafe", "coffee_shop", "bakery", "bagel_shop", "donut_shop", "tea_house",
    "cat_cafe", "dog_cafe", "juice_shop",
}


class PlacesError(Exception):
    """Raised with a human-readable message when a lookup fails."""


class PlaceNotFound(PlacesError):
    """Google no longer recognizes a saved place ID (it can happen; IDs aren't forever)."""


def _is_restaurantish(place_type):
    return place_type.endswith("restaurant") or place_type in {"steak_house", "diner"}


def guess_cuisine(types):
    """First matching cuisine label for a list of Google types (primary type first)."""
    for t in types:
        if t in CUISINE_BY_TYPE:
            return CUISINE_BY_TYPE[t]
    return None


def guess_type(primary_type, types):
    """One of the app's place types: cocktail_bar, breakfast, cafe or restaurant."""
    if primary_type in BAR_TYPES:
        return "cocktail_bar"
    if primary_type in BREAKFAST_TYPES:
        return "breakfast"
    if primary_type in CAFE_TYPES:
        return "cafe"
    if primary_type and _is_restaurantish(primary_type):
        return "restaurant"
    has_bar = any(t in BAR_TYPES for t in types)
    has_restaurant = any(_is_restaurantish(t) for t in types)
    if has_bar and not has_restaurant:
        return "cocktail_bar"
    if any(t in CAFE_TYPES for t in types):
        return "cafe"
    if any(t in BREAKFAST_TYPES for t in types):
        return "breakfast"
    return "restaurant"


def parse_place(p):
    """Turn one raw Places API result into the app's field names."""
    primary = p.get("primaryType") or ""
    types = [primary] + [t for t in p.get("types", []) if t != primary]
    types = [t for t in types if t]

    place_type = guess_type(primary, types)
    cuisine = guess_cuisine(types) or {
        "cocktail_bar": "Cocktails", "cafe": "Coffee & Bakery", "breakfast": "American",
    }.get(place_type, "Other")

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


# ---------- Place Details (live lookup by saved place ID) ----------
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
# Pro + Enterprise fields. (Place Details field masks have no "places." prefix.)
_DETAIL_FIELDS = [
    "id", "displayName", "businessStatus", "googleMapsUri",
    "websiteUri", "nationalPhoneNumber", "rating", "userRatingCount",
]
# `reservable` is an Enterprise + Atmosphere field. Asking for it moves the whole call to
# that billing tier; pass include_reservable=False to stay in the cheaper Enterprise tier.
_RESERVABLE_FIELD = "reservable"


def get_place_details(place_id, api_key, include_reservable=True, timeout=10):
    """Fresh website / phone / rating / reservations info for one saved place ID."""
    fields = _DETAIL_FIELDS + ([_RESERVABLE_FIELD] if include_reservable else [])
    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": ",".join(fields)}
    try:
        resp = requests.get(DETAILS_URL.format(place_id=place_id), headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise PlacesError(f"Couldn't reach Google Places: {e}") from e
    if resp.status_code == 404:
        raise PlaceNotFound("Google no longer recognizes this place's saved link.")
    if resp.status_code != 200:
        raise PlacesError(_error_message(resp))
    p = resp.json()
    return {
        "place_id": p.get("id") or place_id,
        "name": (p.get("displayName") or {}).get("text", ""),
        "closed": p.get("businessStatus") == "CLOSED_PERMANENTLY",
        "maps_url": p.get("googleMapsUri"),
        "website": p.get("websiteUri"),
        "phone": p.get("nationalPhoneNumber"),
        "rating": p.get("rating"),
        "rating_count": p.get("userRatingCount"),
        "reservable": p.get("reservable"),  # True / False / None (unknown)
    }


# ---------- Place Photos (live; never store the photo or its name) ----------
PHOTO_MEDIA_URL = "https://places.googleapis.com/v1/{photo_name}/media"


def get_place_photo(place_id, api_key, max_width_px=800, timeout=10):
    """
    Fetch one fresh photo for a place. Returns None when the place has no photos, else
    {"url": <temporary image URL>, "credit_name": str|None, "credit_uri": str|None}.

    Google's rules: photo names can expire and must not be cached, and any author
    attribution that comes with a photo must be shown next to it. So this makes two
    calls every time (photo name, then the image URL) and keeps nothing.
    """
    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "photos"}
    try:
        resp = requests.get(DETAILS_URL.format(place_id=place_id), headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise PlacesError(f"Couldn't reach Google Places: {e}") from e
    if resp.status_code == 404:
        raise PlaceNotFound("Google no longer recognizes this place's saved link.")
    if resp.status_code != 200:
        raise PlacesError(_error_message(resp))

    photos = resp.json().get("photos") or []
    if not photos:
        return None
    photo = photos[0]
    photo_name = photo.get("name")
    if not photo_name:
        return None

    try:
        media = requests.get(
            PHOTO_MEDIA_URL.format(photo_name=photo_name),
            params={"maxWidthPx": max_width_px, "skipHttpRedirect": "true"},
            headers={"X-Goog-Api-Key": api_key},
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise PlacesError(f"Couldn't load the photo: {e}") from e
    if media.status_code != 200:
        raise PlacesError(_error_message(media))
    uri = media.json().get("photoUri")
    if not uri:
        return None

    author = (photo.get("authorAttributions") or [{}])[0]
    return {
        "url": uri,
        "credit_name": author.get("displayName"),
        "credit_uri": author.get("uri"),
    }
