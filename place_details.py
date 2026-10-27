"""
Live Google details (rating, website, phone, reservations) for saved places.

Only the Google place ID is stored in your database. Details are looked up when you
ask for them (button) or when a place is picked in Random Pick, and cached for a few
hours so repeat views don't use up the free monthly allowance.
"""
import streamlit as st

import places_lookup as pl

CACHE_SECONDS = 6 * 60 * 60


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def _cached_details(place_id, _api_key):
    # The leading underscore keeps the API key out of the cache key.
    return pl.get_place_details(place_id, _api_key)


# ---------- callbacks (run before the next rerun) ----------
def _show_details(key):
    st.session_state[f"gd_show_{key}"] = True


def _find_candidates(r, api_key, key):
    query = f"{r['name']} {r.get('address', '')}".strip()
    try:
        # Pro-tier fields only: no price, so this search is the cheaper kind.
        st.session_state[f"gd_cands_{key}"] = pl.search_places(
            query, api_key, max_results=3, include_price=False
        )
        st.session_state.pop(f"gd_err_{key}", None)
    except pl.PlacesError as e:
        st.session_state[f"gd_cands_{key}"] = []
        st.session_state[f"gd_err_{key}"] = str(e)


def _cancel_link(key):
    st.session_state.pop(f"gd_cands_{key}", None)
    st.session_state.pop(f"gd_err_{key}", None)


def _link_place(r, place, save_data, key):
    r["google_place_id"] = place["place_id"]
    save_data([r])
    _cancel_link(key)
    st.session_state[f"gd_show_{key}"] = True


def _unlink(r, save_data, key):
    r["google_place_id"] = None
    save_data([r])
    st.session_state.pop(f"gd_show_{key}", None)


# ---------- UI pieces ----------
def _render_link_ui(r, key, api_key, save_data):
    """Admin-only: match a saved place to its Google listing (one-time per place)."""
    candidates = st.session_state.get(f"gd_cands_{key}")
    if candidates is None:
        st.button(
            "🔗 Link to Google", key=f"gd_find_{key}",
            on_click=_find_candidates, args=(r, api_key, key),
            help="Matches this place on Google so its rating, website and phone can be shown.",
        )
        return
    err = st.session_state.get(f"gd_err_{key}")
    if err:
        st.error(err)
    elif not candidates:
        st.info("No Google matches found for this name and address.")
    for i, place in enumerate(candidates):
        with st.container(border=True):
            info, action = st.columns([5, 1])
            info.markdown(f"**{place['name']}**  \n{place['address']}")
            action.button(
                "Use", key=f"gd_use_{key}_{i}", on_click=_link_place,
                args=(r, place, save_data, key), use_container_width=True,
            )
    st.button("Cancel", key=f"gd_cancel_{key}", on_click=_cancel_link, args=(key,))


def _render_card(d):
    if d["closed"]:
        st.warning("⚠️ Google lists this place as permanently closed.")

    facts = []
    if d.get("rating") is not None:
        count = f" ({d['rating_count']:,})" if d.get("rating_count") else ""
        facts.append(f"⭐ {d['rating']:.1f}{count}")
    if d.get("reservable") is True:
        facts.append("📅 Takes reservations")
    elif d.get("reservable") is False:
        facts.append("No reservations")
    if d.get("phone"):
        facts.append(f"📞 {d['phone']}")
    if facts:
        st.write("  •  ".join(facts))

    links = []
    if d.get("website"):
        links.append(f"[🌐 Website]({d['website']})")
    if d.get("maps_url"):
        links.append(f"[📍 View on Google Maps]({d['maps_url']})")
    if links:
        st.markdown("  ·  ".join(links))
    if not facts and not links:
        st.caption("Google has no extra details for this place.")
    else:
        st.caption("Live from Google · refreshed every few hours")


def render_google_details(r, key, *, api_key, is_admin, save_data, auto=False):
    """
    Show Google details under a place.

    r         the place dict (needs "google_place_id" to show details)
    key       a string unique to this spot on the page (used for widget keys)
    auto      True = look up right away (Random Pick); False = behind a button, so a
              long list of places doesn't trigger one API call per place on every render
    """
    if not api_key:
        return

    place_id = r.get("google_place_id")
    if not place_id:
        if is_admin:
            _render_link_ui(r, key, api_key, save_data)
        return

    if not (auto or st.session_state.get(f"gd_show_{key}")):
        st.button("🔎 Google details", key=f"gd_btn_{key}", on_click=_show_details, args=(key,))
        return

    try:
        details = _cached_details(place_id, api_key)
    except pl.PlaceNotFound as e:
        st.warning(str(e))
        if is_admin:
            st.button(
                "Unlink so it can be relinked", key=f"gd_unlink_{key}",
                on_click=_unlink, args=(r, save_data, key),
            )
        return
    except pl.PlacesError as e:
        st.warning(str(e))
        return

    _render_card(details)
