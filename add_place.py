"""
"Add a Place" page for the Chicago Eats app, with search-by-name autofill.

Type a name -> pick a result -> name, address, coordinates, cuisine, type, price,
and neighborhood are filled in. The old address-based autofill still works as a
fallback (and is the only mode if GOOGLE_PLACES_API_KEY isn't set).
"""
from datetime import date

import streamlit as st

import places_lookup as pl

PRICES = ["$", "$$", "$$$", "$$$$"]
FORM_KEYS = [
    "add_name", "add_address", "add_cuisine", "add_price", "add_location",
    "add_type", "add_retired", "add_visited", "add_visited_date", "add_images",
    "add_notes", "place_query", "last_place_query", "place_results",
    "place_search_error", "picked_note", "autofill", "last_lookup_address",
]


def render_add_place(*, restaurants, save_data, upload_images, get_lat_lon,
                     lookup_by_address, guess_neighborhood, guess_cuisine_and_type,
                     cuisines, neighborhoods,
                     place_types=("restaurant", "cocktail_bar"), type_labels=None):
    st.header("Add a New Place 📍")
    if not st.session_state.is_admin:
        st.warning("🔒 Admin login required to add places. Use the Admin Login in the sidebar.")
        st.stop()

    type_labels = type_labels or {"restaurant": "Restaurant 🍽️", "cocktail_bar": "Cocktail Bar 🍸"}
    s = st.session_state
    defaults = {
        "add_name": "", "add_address": "", "add_cuisine": cuisines[0],
        "add_price": "$$", "add_location": neighborhoods[0], "add_type": "restaurant",
        "add_retired": False, "add_visited": False, "add_notes": "",
    }
    for key, value in defaults.items():
        s.setdefault(key, value)

    # ---------- Pick-a-result callback (runs before the next rerun) ----------
    def apply_pick(place):
        s["add_name"] = place["name"]
        s["add_address"] = place["address"]
        s["add_cuisine"] = place["cuisine"] if place["cuisine"] in cuisines else "Other"
        if place["price"]:
            s["add_price"] = place["price"]
        hood = guess_neighborhood(place["latitude"], place["longitude"])
        if hood in neighborhoods:
            s["add_location"] = hood
        s["add_type"] = place["type"]
        s["add_retired"] = bool(place["closed"])
        # Same shape the address-lookup uses, so "Add Place" reuses these coordinates
        s["autofill"] = {
            "address": place["address"],
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "cuisine": s["add_cuisine"],
            "location": s["add_location"],
            "type": place["type"],
            "place_id": place["place_id"],
        }
        s["last_lookup_address"] = place["address"]  # skip the address re-lookup
        s["picked_note"] = (
            f"Filled in from **{place['name']}**."
            + ("" if place["price"] else " No price info found - set it yourself.")
            + (" ⚠️ Google lists this place as permanently closed, so Retired is ticked."
               if place["closed"] else "")
        )
        s["place_results"] = []
        s["place_query"] = ""
        s["last_place_query"] = ""

    # ---------- Search by name ----------
    google_key = st.secrets.get("GOOGLE_PLACES_API_KEY", "")
    if google_key:
        query = st.text_input(
            "🔎 Find a place by name",
            key="place_query",
            placeholder="e.g. Au Cheval, Fulton Market",
            help="Pick a result below and the form fills itself in. Adding an area helps for chains.",
        )
        q = query.strip()
        if q and q != s.get("last_place_query"):
            s["last_place_query"] = q
            try:
                with st.spinner("Searching..."):
                    s["place_results"] = pl.search_places(q, google_key)
                s["place_search_error"] = None
            except pl.PlacesError as e:
                s["place_results"] = []
                s["place_search_error"] = str(e)

        if s.get("place_search_error"):
            st.error(s["place_search_error"])
        elif s.get("place_results"):
            for i, place in enumerate(s["place_results"]):
                with st.container(border=True):
                    info, action = st.columns([5, 1])
                    info.markdown(f"**{place['name']}**  \n{place['address']}")
                    action.button("Use", key=f"use_place_{i}", on_click=apply_pick,
                                  args=(place,), use_container_width=True)
        elif q and q == s.get("last_place_query"):
            st.info("No matches. Try adding the neighborhood, or fill in the form by hand.")
        if s.get("picked_note"):
            st.success(s["picked_note"])
        st.markdown("---")
    else:
        st.caption(
            "Tip: add GOOGLE_PLACES_API_KEY to your Streamlit secrets to search by name. "
            "For now, the address field fills in neighborhood and (when recognized) cuisine."
        )

    # ---------- The form ----------
    name = st.text_input("Name*", key="add_name")
    address = st.text_input(
        "Address*", key="add_address",
        help="Neighborhood (and cuisine/type, when we can tell) fill in automatically once you enter this.",
    )

    # Address-based autofill (fallback). Runs once per distinct address typed.
    clean_address = address.strip()
    if clean_address and clean_address != s.get("last_lookup_address"):
        with st.spinner("Looking up that address..."):
            found = lookup_by_address(clean_address)
        s["last_lookup_address"] = clean_address
        if found:
            guessed_cuisine, guessed_type = guess_cuisine_and_type(found.get("category"))
            guessed_hood = guess_neighborhood(found["latitude"], found["longitude"])
            # These widgets are created further down this run, so setting them here is safe.
            if guessed_cuisine in cuisines:
                s["add_cuisine"] = guessed_cuisine
            if guessed_hood in neighborhoods:
                s["add_location"] = guessed_hood
            s["add_type"] = guessed_type
            s["autofill"] = {
                "address": clean_address,
                "latitude": found["latitude"],
                "longitude": found["longitude"],
                "cuisine": guessed_cuisine,
                "location": guessed_hood,
                "type": guessed_type,
            }
            st.rerun()
        else:
            s["autofill"] = {}
            st.warning("⚠️ Couldn't locate that address — you can still fill in the fields below by hand.")

    autofill = s.get("autofill", {})
    if autofill.get("address") == clean_address and autofill.get("latitude"):
        st.caption("📍 Location found. Fields below were filled in automatically — adjust anything that's off.")

    cuisine = st.selectbox("Cuisine/Style*", cuisines, key="add_cuisine")
    price = st.selectbox("Price*", PRICES, key="add_price")
    location = st.selectbox("Neighborhood*", neighborhoods, key="add_location")
    place_type = st.selectbox(
        "Type*", list(place_types), key="add_type",
        format_func=lambda x: type_labels.get(x, x),
    )
    retired = st.checkbox("😔 Retired?", key="add_retired")
    visited = st.checkbox("✅ I've already visited this place", key="add_visited")
    visited_date = (
        st.date_input("Date Visited", value=date.today(), key="add_visited_date")
        if visited else None
    )
    uploaded_images = st.file_uploader("Upload photos", accept_multiple_files=True, key="add_images")
    quick_notes = st.text_area("Quick notes (optional)", height=100, key="add_notes")

    if st.button("Add Place", type="primary"):
        if not all([name.strip(), address.strip()]):
            st.error("Name and address required")
        elif any(r["name"].lower() == name.lower().strip() for r in restaurants):
            st.warning("Already exists!")
        else:
            # Reuse coordinates from autofill if the address wasn't edited afterward.
            lat, lon = None, None
            if autofill.get("address") == address.strip() and autofill.get("latitude"):
                lat, lon = autofill["latitude"], autofill["longitude"]
            else:
                with st.spinner(f"Locating '{address}'..."):
                    lat, lon = get_lat_lon(address.strip())
            if lat is None:
                st.warning("⚠️ Could not find coordinates. Place will save but won't appear on map.")
            else:
                st.toast("✅ Location found!")

            image_urls = []
            if uploaded_images:
                with st.spinner("Uploading images..."):
                    image_urls = upload_images(uploaded_images, name)

            # Keep the Google place ID only if the address wasn't edited after picking.
            google_place_id = (
                autofill.get("place_id") if autofill.get("address") == address.strip() else None
            )

            new = {
                "name": name.strip(),
                "cuisine": cuisine,
                "price": price,
                "location": location,
                "address": address.strip(),
                "type": place_type,
                "favorite": False,
                "visited": visited,
                "visited_date": visited_date.strftime("%B %d, %Y") if visited_date else None,
                "reviews": [quick_notes.strip()] if quick_notes.strip() else [],
                "images": image_urls,
                "latitude": lat,
                "longitude": lon,
                "retired": retired,
                "google_place_id": google_place_id,
            }
            inserted = save_data([new])
            if inserted:
                restaurants.append(inserted)
                for key in FORM_KEYS:
                    try:
                        del s[key]
                    except KeyError:
                        pass
                s.success_message = f"{name} added successfully!"
                st.rerun()
            else:
                st.error("Failed to add place.")
