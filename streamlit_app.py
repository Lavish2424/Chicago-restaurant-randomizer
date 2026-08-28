import streamlit as st
import random
import urllib.parse
from datetime import datetime, date
from supabase import create_client, Client
import os
from streamlit_folium import st_folium
import folium
from geopy.geocoders import ArcGIS
import time
from folium.plugins import LocateControl, MarkerCluster
from PIL import Image, ExifTags, ImageOps  # ADDED: For image resizing/fixing
import io  # ADDED: For handling image byte streams

# ==================== PAGE CONFIG (must be first Streamlit call) ====================
st.set_page_config(
    page_title="Chicago Eats & Drinks",
    page_icon="🥃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================== VISUAL IDENTITY ====================
# Vintage supper-club / marquee-sign direction: ink-black rooms, brass marquee
# lettering, a wine accent for favorites, and ticket-stub styling for entries.
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Work+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --ink: #1B1712;
    --ledger: #241F18;
    --ledger-light: #2E271D;
    --brass: #C9A034;
    --brass-bright: #E3C066;
    --wine: #8B2A3B;
    --wine-bright: #E8A6B4;
    --cream: #F1E9D8;
    --smoke: #A79A85;
    --green: #6B8863;
    --hairline: rgba(201, 160, 52, 0.28);
}

html, body, [data-testid="stAppViewContainer"], .main {
    background-color: var(--ink) !important;
    color: var(--cream) !important;
    font-family: 'Work Sans', sans-serif;
}
[data-testid="stHeader"] { background-color: transparent !important; }

[data-testid="stSidebar"] {
    background-color: var(--ledger) !important;
    border-right: 1px solid var(--hairline);
}
[data-testid="stSidebar"] * { color: var(--cream) !important; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    font-family: 'Fraunces', serif !important;
}

h1, h2, h3 {
    font-family: 'Fraunces', serif !important;
    color: var(--brass-bright) !important;
    letter-spacing: 0.01em;
}

/* ---------- Hero marquee ---------- */
.marquee-hero {
    text-align: center;
    padding: 1.5rem 1rem 1.35rem;
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 1.75rem;
}
.marquee-hero h1 {
    font-family: 'Fraunces', serif !important;
    font-size: 2.6rem;
    font-weight: 700;
    color: var(--brass-bright) !important;
    margin: 0;
    text-shadow: 0 0 26px rgba(227, 192, 102, 0.28);
}
.marquee-hero p {
    font-family: 'IBM Plex Mono', monospace;
    color: var(--smoke);
    letter-spacing: 0.22em;
    text-transform: uppercase;
    font-size: 0.7rem;
    margin-top: 0.55rem;
}

/* ---------- Buttons ---------- */
.stButton > button,
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"] {
    font-family: 'Work Sans', sans-serif !important;
    background-color: var(--ledger-light) !important;
    color: var(--cream) !important;
    border: 1px solid var(--hairline) !important;
    border-radius: 4px !important;
    transition: border-color 0.15s ease, color 0.15s ease;
}
.stButton > button:hover { border-color: var(--brass) !important; color: var(--brass-bright) !important; }
button[kind="primary"], [data-testid="stBaseButton-primary"] {
    background-color: var(--brass) !important;
    color: var(--ink) !important;
    font-weight: 600 !important;
    border: none !important;
}
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
    background-color: var(--brass-bright) !important;
    color: var(--ink) !important;
}

/* ---------- Expander -> ticket stub ---------- */
[data-testid="stExpander"] {
    background-color: var(--ledger) !important;
    border: 1px solid var(--hairline) !important;
    border-left: 3px dashed var(--brass) !important;
    border-radius: 6px !important;
    margin-bottom: 0.6rem;
}
[data-testid="stExpander"] summary { font-family: 'Fraunces', serif !important; font-size: 1.05rem; }
[data-testid="stExpander"] summary:hover { color: var(--brass-bright) !important; }

/* ---------- Inputs ---------- */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-baseweb="select"] > div,
[data-testid="stDateInput"] input {
    background-color: var(--ledger-light) !important;
    color: var(--cream) !important;
    border: 1px solid var(--hairline) !important;
    border-radius: 4px !important;
    font-family: 'Work Sans', sans-serif !important;
}

/* ---------- Badges ---------- */
.badge-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.4rem 0 1rem; }
.badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.02em;
    padding: 0.22rem 0.62rem;
    border-radius: 999px;
    border: 1px solid var(--hairline);
    color: var(--cream);
    background-color: var(--ledger-light);
    white-space: nowrap;
}
.badge-type { border-color: var(--brass); color: var(--brass-bright); }
.badge-fav { border-color: var(--wine); color: var(--wine-bright); background-color: rgba(139, 42, 59, 0.18); }
.badge-visited { border-color: var(--green); color: #C3D6BC; background-color: rgba(107, 136, 99, 0.18); }
.badge-retired { border-color: var(--smoke); color: var(--smoke); }

/* ---------- Random-pick ticket ---------- */
.ticket {
    position: relative;
    background: linear-gradient(180deg, var(--ledger) 0%, var(--ledger-light) 100%);
    border: 1px solid var(--hairline);
    border-radius: 10px;
    padding: 1.6rem 1.75rem 1.1rem 2.1rem;
    margin-bottom: 0.5rem;
    overflow: hidden;
}
.ticket::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background-image: linear-gradient(90deg, var(--brass) 50%, transparent 50%);
    background-size: 14px 4px;
}
.ticket-eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: var(--brass);
}
.ticket h1 {
    font-family: 'Fraunces', serif !important;
    font-size: 2.05rem;
    margin: 0.3rem 0 0 !important;
    color: var(--brass-bright) !important;
}

.spin-frame {
    text-align: center;
    font-family: 'Fraunces', serif;
    font-size: 1.9rem;
    color: var(--brass-bright);
    padding: 0.5rem 0;
}

@keyframes ticketDrop {
    0% { opacity: 0; transform: translateY(-20px) rotate(0deg) scale(0.96); }
    60% { opacity: 1; transform: translateY(4px) rotate(-2.6deg) scale(1.02); }
    100% { opacity: 1; transform: translateY(0) rotate(-1.4deg) scale(1); }
}
@keyframes stampDown {
    0% { opacity: 0; transform: rotate(-14deg) scale(2.4); }
    70% { opacity: 0.95; transform: rotate(-14deg) scale(0.9); }
    100% { opacity: 0.92; transform: rotate(-14deg) scale(1); }
}
.ticket {
    animation: ticketDrop 0.55s cubic-bezier(.34, 1.56, .64, 1) both;
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.5);
    overflow: visible;
}
/* torn perforation along the left edge, as if pulled from a ticket book */
.ticket::after {
    content: "";
    position: absolute;
    top: -3px; bottom: -3px; left: -3px;
    width: 17px;
    background-image:
        linear-gradient(135deg, var(--ink) 8px, transparent 8.5px),
        linear-gradient(225deg, var(--ink) 8px, transparent 8.5px);
    background-size: 17px 17px;
    background-repeat: repeat-y;
    background-position: left top;
}
.ticket-stamp {
    position: absolute;
    top: 16px;
    right: 20px;
    padding: 0.4rem 1rem;
    border: 3px double var(--wine);
    border-radius: 50%;
    color: var(--wine-bright);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    animation: stampDown 0.4s cubic-bezier(.2, 1.6, .4, 1) 0.4s both;
}

/* ---------- Misc ---------- */
#success-banner {
    font-family: 'Work Sans', sans-serif;
    background-color: var(--brass) !important;
    color: var(--ink) !important;
    font-weight: 600;
    border: none !important;
}
hr { border-color: var(--hairline) !important; }
[data-testid="stCaptionContainer"], .stCaption, small { color: var(--smoke) !important; }
[data-testid="stImage"] img { border-radius: 6px; border: 1px solid var(--hairline); }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ==================== SUPABASE SETUP ====================
try:
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_ANON_KEY"]
except FileNotFoundError:
    st.error("Secrets not found. Please set up your .streamlit/secrets.toml file.")
    st.stop()
supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"
# Initialize ArcGIS Geocoder
geolocator = ArcGIS(timeout=10)
# ==================== HELPER FUNCTIONS ====================
def get_lat_lon(address):
    """Converts an address string to latitude and longitude using ArcGIS."""
    try:
        time.sleep(1)  # 1-second delay to avoid throttling
        clean_addr = address.strip()
        if not clean_addr:
            return None, None
        if "chicago" not in clean_addr.lower() and "il" not in clean_addr.lower():
            search_query = f"{clean_addr}, Chicago, IL"
        else:
            search_query = clean_addr
        for attempt in range(3):
            try:
                location = geolocator.geocode(search_query)
                if location:
                    return location.latitude, location.longitude
                return None, None
            except Exception as e:
                if "timeout" in str(e).lower() or "rate" in str(e).lower():
                    time.sleep(2 ** attempt)
                else:
                    raise e
        st.warning("Geocoding failed after retries.")
        return None, None
    except Exception as e:
        st.error(f"Geocoding error: {e}")
        return None, None
def load_data():
    try:
        response = supabase.table("restaurants").select("*").execute()
        data = response.data
        for place in data:
            place.setdefault("favorite", False)
            place.setdefault("visited", False)
            place.setdefault("visited_date", None)
            place.setdefault("reviews", [])
            place.setdefault("images", [])
            place.setdefault("latitude", None)
            place.setdefault("longitude", None)
            place.setdefault("retired", False)
            place.setdefault("created_at", None)
            normalized = []
            for rev in place.get("reviews", []):
                if rev:
                    if isinstance(rev, dict) and "comment" in rev:
                        cleaned = str(rev["comment"]).strip()
                    elif isinstance(rev, str):
                        cleaned = str(rev).strip()
                    else:
                        cleaned = ""
                    if cleaned:
                        normalized.append(cleaned)
            place["reviews"] = normalized
        return data
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return []
def save_data(data):
    try:
        for place in data:
            place_id = place.get("id")
            update_data = {
                "name": place["name"],
                "cuisine": place["cuisine"],
                "price": place["price"],
                "location": place["location"],
                "address": place["address"],
                "type": place["type"],
                "favorite": place.get("favorite", False),
                "visited": place.get("visited", False),
                "visited_date": place.get("visited_date"),
                "reviews": place["reviews"],
                "images": place.get("images", []),
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
                "retired": place.get("retired", False),
            }
            if place.get("created_at") is None:
                # Let DB set default on insert
                pass
            else:
                update_data["created_at"] = place["created_at"]
            if place_id:
                supabase.table("restaurants").update(update_data).eq("id", place_id).execute()
            else:
                response = supabase.table("restaurants").insert(update_data).execute()
                if response.data:
                    return response.data[0]
        return None
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return None
def delete_restaurant(index):
    r = restaurants[index]

    # 1. DELETE THE ACTUAL FILES FROM STORAGE BUCKET
    if r.get("images"):
        paths_to_delete = []
        for url in r["images"]:
            try:
                # We need to turn the full URL into just the 'folder/file.jpg' path
                # Example URL: https://xyz.supabase.co/storage/v1/object/public/restaurant-images/Tacos/pic.jpg
                # We need: Tacos/pic.jpg
                if BUCKET_NAME in url:
                    # Split the URL by the bucket name and take everything after it
                    file_path = url.split(f"{BUCKET_NAME}/")[-1]
                    paths_to_delete.append(file_path)
            except Exception as e:
                st.warning(f"Could not figure out storage path for: {url}")
        if paths_to_delete:
            try:
                # 1. Try deleting the calculated paths
                supabase.storage.from_(BUCKET_NAME).remove(paths_to_delete)
            except Exception as e:
                # 2. If that fails, try a 'lazy' search for the filename
                # (This helps fix old entries with broken paths)
                for path in paths_to_delete:
                    try:
                        filename = path.split('/')[-1]
                        # Look for the file in the root if it's not in the folder
                        supabase.storage.from_(BUCKET_NAME).remove([filename])
                    except:
                        pass
    # 2. DELETE THE ROW FROM THE DATABASE TABLE
    # This is what makes it disappear from your app (and stay gone after reboot)
    if "id" in r:
        try:
            supabase.table("restaurants").delete().eq("id", r["id"]).execute()
        except Exception as e:
            st.error(f"Database delete failed: {e}")
            return
    # 3. REFRESH APP
    del restaurants[index]
    st.session_state.success_message = f"Removed {r['name']} and its photos."
    st.rerun()
def toggle_favorite(idx):
    restaurants[idx]["favorite"] = not restaurants[idx].get("favorite", False)
    save_data([restaurants[idx]])
    st.rerun()
def toggle_visited(idx):
    restaurants[idx]["visited"] = not restaurants[idx].get("visited", False)
    save_data([restaurants[idx]])
    st.rerun()
def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

# ==================== AUTO-FILL HELPERS ====================
# Rough lat/lon centers for each neighborhood, used to guess the closest
# match once we have coordinates for a place — saves picking it by hand.
NEIGHBORHOOD_CENTROIDS = {
    "Berwyn": (41.8506, -87.7939),
    "Chinatown": (41.8517, -87.6326),
    "Fulton Market": (41.8869, -87.6503),
    "Gold Coast": (41.9066, -87.6296),
    "Lincoln Park": (41.9214, -87.6513),
    "Logan Square": (41.9236, -87.7079),
    "Near North Side": (41.8994, -87.6338),
    "Oakbrook": (41.8394, -87.9503),
    "Oak Lawn": (41.7200, -87.7581),
    "Pilsen": (41.8563, -87.6564),
    "River North": (41.8919, -87.6343),
    "South Loop": (41.8664, -87.6270),
    "West Loop": (41.8849, -87.6534),
    "West Town": (41.8963, -87.6752),
    "Wicker Park": (41.9088, -87.6796),
}

# Keyword -> cuisine label, checked in order (first match wins).
CUISINE_KEYWORDS = [
    ("pizza", "Italian"),
    ("italian", "Italian"),
    ("taco", "Mexican"),
    ("mexican", "Mexican"),
    ("chinese", "Chinese"),
    ("dim sum", "Chinese"),
    ("sushi", "Japanese"),
    ("japanese", "Japanese"),
    ("ramen", "Japanese"),
    ("thai", "Thai"),
    ("indian", "Indian"),
    ("french", "French"),
    ("bistro", "French"),
    ("tapas", "Spanish"),
    ("spanish", "Spanish"),
    ("greek", "Mediterranean"),
    ("mediterranean", "Mediterranean"),
    ("seafood", "Seafood"),
    ("steak", "Steakhouse"),
    ("cocktail", "Cocktails"),
    ("lounge", "Cocktails"),
    ("wine bar", "Cocktails"),
    ("asian", "Asian"),
]
# Keywords that suggest this POI is a bar rather than a restaurant.
BAR_KEYWORDS = ["bar", "lounge", "pub", "tavern", "cocktail", "brewery", "speakeasy"]


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in miles."""
    from math import radians, sin, cos, sqrt, atan2
    r = 3958.8
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def guess_neighborhood(lat, lon):
    """Nearest of our known Chicago-area neighborhoods to a coordinate."""
    if lat is None or lon is None:
        return None
    name, _ = min(
        NEIGHBORHOOD_CENTROIDS.items(),
        key=lambda kv: haversine_miles(lat, lon, kv[1][0], kv[1][1]),
    )
    return name


def guess_cuisine_and_type(category_text):
    """Best-effort cuisine + restaurant/bar guess from an ArcGIS POI category string."""
    text = (category_text or "").lower()
    place_type = "cocktail_bar" if any(k in text for k in BAR_KEYWORDS) else "restaurant"
    cuisine = "Other"
    for keyword, label in CUISINE_KEYWORDS:
        if keyword in text:
            cuisine = label
            break
    return cuisine, place_type


def lookup_place_by_address(address):
    """
    Geocode an address via ArcGIS and return whatever we can auto-fill from it:
    coordinates (for the neighborhood guess) and a category string, if ArcGIS's
    match happens to be a recognized business listing rather than a bare street
    address — used to guess cuisine/type. Returns None if geocoding fails.
    """
    try:
        time.sleep(1)  # same throttle guard as get_lat_lon
        clean_addr = address.strip()
        if not clean_addr:
            return None
        if "chicago" not in clean_addr.lower() and "il" not in clean_addr.lower():
            search_query = f"{clean_addr}, Chicago, IL"
        else:
            search_query = clean_addr
        location = geolocator.geocode(search_query, exactly_one=True, out_fields="*")
        if not location:
            return None
        raw = location.raw or {}
        attrs = raw.get("attributes", {})
        # ArcGIS's business-listing matches carry a category in "Type" or
        # "PlaceName" depending on the source dataset — check both. A plain
        # street address usually won't have either, and that's fine: we
        # still get coordinates for the neighborhood guess.
        category = attrs.get("Type") or attrs.get("PlaceName") or ""
        return {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "category": category,
        }
    except Exception as e:
        st.warning(f"Auto-fill lookup failed: {e}")
        return None

# ---------- Visual helpers ----------
def badge_html(text, kind=""):
    cls = f"badge {kind}".strip()
    return f'<span class="{cls}">{text}</span>'

def render_badges(r):
    """Renders a tidy pill row (cuisine / price / neighborhood / type / status) for a place."""
    parts = [
        badge_html(r["cuisine"]),
        badge_html(r["price"]),
        badge_html(r["location"]),
        badge_html("Cocktail Bar" if r.get("type") == "cocktail_bar" else "Restaurant", "badge-type"),
    ]
    if r.get("favorite"):
        parts.append(badge_html("♥ Favorite", "badge-fav"))
    if r.get("visited"):
        vis_label = "Visited" + (f" · {r['visited_date']}" if r.get("visited_date") else "")
        parts.append(badge_html(vis_label, "badge-visited"))
    if r.get("retired", False):
        parts.append(badge_html("Retired", "badge-retired"))
    st.markdown(f'<div class="badge-row">{"".join(parts)}</div>', unsafe_allow_html=True)

def spin_frame(name):
    return f'<div class="spin-frame">🎲 &nbsp;{name}</div>'

# Delay (seconds) between frames, front-loaded fast and slowing toward the end
# so the draw feels like it's settling on an answer rather than just flickering.
SPIN_SCHEDULE_MAIN = [0.02] * 10 + [0.03] * 8 + [0.05] * 6 + [0.08] * 5 + [0.12] * 4 + [0.18] * 3
SPIN_SCHEDULE_AGAIN = [0.02] * 6 + [0.04] * 5 + [0.07] * 4 + [0.11] * 3 + [0.16] * 2

def run_spin(placeholder, choices, schedule):
    for delay in schedule:
        temp_pick = random.choice(choices)
        placeholder.markdown(spin_frame(temp_pick["name"]), unsafe_allow_html=True)
        time.sleep(delay)
    placeholder.empty()

# REPLACED FUNCTION: Now handles resizing and compression
def upload_images_to_supabase(uploaded_files, restaurant_name):
    urls = []
    # Sanitize name for the file path
    sanitized_name = "".join(c for c in restaurant_name if c.isalnum() or c in " -_").rstrip()
    for i, file in enumerate(uploaded_files):
        # 1. PROCESS THE IMAGE (Resize & Compress)
        try:
            image = Image.open(file)

            # Fix orientation (handle EXIF rotation common in phone photos)
            image = ImageOps.exif_transpose(image)

            # Convert to RGB (in case of PNG/RGBA) to allow JPEG saving
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            # Resize if too large (max width/height 1200px)
            max_size = (1200, 1200)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            # Save to a byte buffer as optimized JPEG
            output_buffer = io.BytesIO()
            image.save(output_buffer, format="JPEG", quality=80, optimize=True)
            file_data = output_buffer.getvalue()

            # Force extension to .jpg since we converted it
            filename = f"{sanitized_name}_{i}_{int(time.time())}.jpg"
            mime_type = "image/jpeg"
        except Exception as e:
            st.error(f"Error processing image {file.name}: {e}")
            continue
        file_path = f"{sanitized_name}/{filename}"
        # 2. UPLOAD TO SUPABASE
        for attempt in range(3):
            try:
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=file_path,
                    file=file_data,  # Use our compressed data, not the original file
                    file_options={"content-type": mime_type, "upsert": "true"}
                )
                public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
                urls.append(public_url)
                st.toast(f"Uploaded {file.name}")
                break
            except Exception as e:
                if attempt == 2:
                    st.error(f"Failed to upload {file.name} after 3 attempts: {type(e).__name__} – {str(e)}")
                else:
                    time.sleep(1.5 * (attempt + 1))
                    st.info(f"Retrying upload for {file.name} (attempt {attempt+2}/3)...")
    return urls
# ==================== APP LOGIC ====================
if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()
restaurants = st.session_state.restaurants

st.markdown(
    """
    <div class="marquee-hero">
        <h1>Chicago Eats &amp; Drinks</h1>
        <p>Restaurants · Cocktail Bars · Pick Your Next Spot</p>
    </div>
    """,
    unsafe_allow_html=True,
)
# Success banner
if "success_message" in st.session_state:
    message = st.session_state.success_message
    st.markdown(
        f"""
        <div id="success-banner" style="position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
             background-color: #28a745; color: white; padding: 10px 20px; border-radius: 5px;
             box-shadow: 0 2px 4px rgba(0,0,0,0.2); z-index: 1000; text-align: center;">
            {message}
        </div>
        <script>
            setTimeout(function() {{
                var banner = document.getElementById('success-banner');
                if (banner) {{ banner.style.display = 'none'; }}
            }}, 5000);
        </script>
        """,
        unsafe_allow_html=True
    )
    del st.session_state.success_message
st.sidebar.header("Actions")

# ==================== ADMIN LOGIN ====================
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

with st.sidebar.expander("🔓 Admin Mode" if st.session_state.is_admin else "🔒 Admin Login"):
    if st.session_state.is_admin:
        st.success("Logged in as admin")
        if st.button("Log out", key="admin_logout_btn", use_container_width=True):
            st.session_state.is_admin = False
            st.rerun()
    else:
        admin_pwd = st.text_input("Password", type="password", key="admin_pwd_input")
        if st.button("Log in", key="admin_login_btn", use_container_width=True):
            if admin_pwd and admin_pwd == st.secrets.get("APP_PASSWORD", ""):
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("Incorrect password")

action = st.sidebar.radio(
    "What do you want to do?",
    ["📖 View All Places", "🗺️ Map View", "➕ Add a Place", "🎲 Random Pick"],
)
st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")
# Clear session state on action change
if "previous_action" not in st.session_state:
    st.session_state.previous_action = action
if st.session_state.previous_action != action:
    keys_to_clear = [k for k in st.session_state.keys() if k.startswith(("edit_mode_", "images_to_delete_", "del_confirm_", "edit_reviews_"))]
    for k in keys_to_clear:
        del st.session_state[k]
    if "last_pick" in st.session_state:
        del st.session_state.last_pick
    if "autofill" in st.session_state:
        del st.session_state.autofill
    if "last_lookup_address" in st.session_state:
        del st.session_state.last_lookup_address
    st.session_state.previous_action = action
NEIGHBORHOODS = [
    "Berwyn",
    "Chinatown",
    "Fulton Market",
    "Gold Coast",
    "Lincoln Park",
    "Logan Square",
    "Near North Side",
    "Oakbrook",
    "Oak Lawn",
    "Pilsen",
    "River North",
    "South Loop",
    "West Loop",
    "West Town",
    "Wicker Park"
]
CUISINES = [
    "American",
    "Asian",
    "Chinese",
    "Cocktails",
    "French",
    "Indian",
    "Italian",
    "Japanese",
    "Mediterranean",
    "Mexican",
    "Other",
    "Seafood",
    "Spanish",
    "Steakhouse",
    "Thai"
]
VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]
# ────────────────────────────── View All Places ──────────────────────────────
if action == "📖 View All Places":
    st.header("All Places 👀")
    st.caption(f"{len(restaurants)} place(s)")
    if not restaurants:
        st.info("No places added yet.")
    else:
        col_search, col_sort = st.columns([5, 3])
        with col_search:
            search_term = st.text_input("🔍 Search name, cuisine, neighborhood, address", key="search_input")
        with col_sort:
            sort_option = st.selectbox(
                "Sort by",
                ["A-Z (Name)", "Favorites First", "Recently Added", "Oldest First", "Not Visited First"]
            )
        filtered = restaurants.copy()
        if search_term:
            lower = search_term.lower()
            filtered = [r for r in filtered if lower in r["name"].lower() or
                        lower in r["cuisine"].lower() or lower in r["location"].lower() or
                        lower in r.get("address", "").lower()]
        if sort_option == "A-Z (Name)":
            sorted_places = sorted(filtered, key=lambda x: x["name"].lower())
        elif sort_option == "Favorites First":
            sorted_places = sorted([r for r in filtered if r.get("favorite")], key=lambda x: x["name"].lower()) + \
                            sorted([r for r in filtered if not r.get("favorite")], key=lambda x: x["name"].lower())
        elif sort_option == "Recently Added":
            sorted_places = sorted(
                filtered,
                key=lambda x: datetime.fromisoformat(x.get("created_at", "1900-01-01T00:00:00")).replace(tzinfo=None)
                if x.get("created_at") else datetime.min,
                reverse=True
            )
        elif sort_option == "Oldest First":
            sorted_places = sorted(
                filtered,
                key=lambda x: datetime.fromisoformat(x.get("created_at", "1900-01-01T00:00:00")).replace(tzinfo=None)
                if x.get("created_at") else datetime.min
            )
        elif sort_option == "Not Visited First":
            sorted_places = sorted([r for r in filtered if not r.get("visited")], key=lambda x: x["name"].lower()) + \
                            sorted([r for r in filtered if r.get("visited")], key=lambda x: x["name"].lower())
        else:
            sorted_places = filtered
        for idx, r in enumerate(sorted_places):
            global_idx = restaurants.index(r)
            icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
            fav = " ❤️" if r.get("favorite") else ""
            visited = " ✅" if r.get("visited") else ""
            visited_date_str = f" (visited {r['visited_date']})" if r.get("visited") and r.get("visited_date") else ""
            retired_str = " (Retired)" if r.get("retired", False) else ""
            img_count = f" • {len(r.get('images', []))} photo{'s' if len(r.get('images', [])) > 1 else ''}" if r.get("images") else ""
            notes_count = f" • {len(r['reviews'])} note{'s' if len(r['reviews']) != 1 else ''}" if r["reviews"] else ""
            with st.expander(f"{r['name']}{icon}{fav}{visited}{visited_date_str}{retired_str} • {r['cuisine']} • {r['price']} • {r['location']}{img_count}{notes_count}",
                             expanded=(f"edit_mode_{global_idx}" in st.session_state)):
                if f"edit_mode_{global_idx}" not in st.session_state:
                    if st.session_state.is_admin:
                        btn1, btn2, btn3, btn4 = st.columns(4)
                        with btn1:
                            if st.button("❤️ Favorite" if not r.get("favorite") else "💔 Unfavorite", key=f"fav_{global_idx}", use_container_width=True):
                                toggle_favorite(global_idx)
                        with btn2:
                            if st.button("✅ Mark Visited" if not r.get("visited") else "❌ Mark Unvisited", key=f"vis_{global_idx}", type="secondary", use_container_width=True):
                                toggle_visited(global_idx)
                        with btn3:
                            if st.button("Edit ✏️", key=f"edit_{global_idx}", use_container_width=True):
                                st.session_state[f"edit_mode_{global_idx}"] = True
                                st.rerun()
                        with btn4:
                            delete_key = f"del_confirm_{global_idx}"
                            if delete_key in st.session_state:
                                if st.button("🗑️ Confirm Delete", type="primary", key=f"conf_{global_idx}", use_container_width=True):
                                    delete_restaurant(global_idx)
                            else:
                                if st.button("Delete 🗑️", key=f"del_{global_idx}", use_container_width=True):
                                    st.session_state[delete_key] = True
                                    st.rerun()
                        if delete_key in st.session_state:
                            if st.button("Cancel Delete", key=f"can_{global_idx}", use_container_width=True):
                                del st.session_state[delete_key]
                                st.rerun()
                    render_badges(r)
                    col_addr, col_map = st.columns([3, 1])
                    with col_addr:
                        st.write(f"**📍 Address:** {r.get('address', 'Not provided')}")
                        if not r.get("latitude"):
                            st.caption("⚠️ No coordinates found for map.")
                    with col_map:
                        st.markdown(f"[🗺️ Open in Maps]({google_maps_link(r.get('address', ''), r['name'])})", unsafe_allow_html=True)
                    if r["reviews"]:
                        st.markdown("**📝 Notes**")
                        for note in reversed(r["reviews"]):
                            if note and str(note).strip():
                                with st.container(border=True):
                                    st.write(str(note).strip())
                    else:
                        st.caption("_No notes yet — be the first to add one!_")
                    if r.get("images"):
                        st.markdown("**📸 Photos**")
                        num_images = len(r["images"])
                        for i in range(0, num_images, 3):
                            cols = st.columns(3)
                            for j in range(3):
                                idx_img = i + j
                                if idx_img < num_images:
                                    with cols[j]:
                                        st.image(r["images"][idx_img], width="stretch")
                else:
                    # EDIT MODE
                    st.subheader(f"Editing: {r['name']}")
                    images_to_delete_key = f"images_to_delete_{global_idx}"
                    reviews_key = f"edit_reviews_{global_idx}"
                    edit_name = st.text_input("Name", value=r["name"], key=f"edit_name_{global_idx}")
                    edit_cuisine = st.selectbox("Cuisine/Style", CUISINES,
                                                index=CUISINES.index(r["cuisine"]) if r["cuisine"] in CUISINES else 0,
                                                key=f"edit_cuisine_{global_idx}")
                    edit_price = st.selectbox("Price", ["$", "$$", "$$$", "$$$$"],
                                              index=["$", "$$", "$$$", "$$$$"].index(r["price"]),
                                              key=f"edit_price_{global_idx}")
                    edit_location = st.selectbox("Neighborhood", NEIGHBORHOODS,
                                                 index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else 0,
                                                 key=f"edit_location_{global_idx}")
                    edit_address = st.text_input("Address", value=r["address"], key=f"edit_address_{global_idx}")
                    edit_type = st.selectbox("Type", ["restaurant", "cocktail_bar"],
                                             index=0 if r["type"] == "restaurant" else 1,
                                             format_func=lambda x: "Restaurant 🍽️" if x == "restaurant" else "Cocktail Bar 🍸",
                                             key=f"edit_type_{global_idx}")
                    edit_retired = st.checkbox("😔 Retired?", value=r.get("retired", False), key=f"edit_retired_{global_idx}")
                    edit_visited = st.checkbox("✅ I've already visited this place", value=r.get("visited", False),
                                               key=f"edit_visited_{global_idx}")
                    existing_date = None
                    if r.get("visited_date"):
                        try:
                            existing_date = datetime.strptime(r["visited_date"], "%B %d, %Y").date()
                        except:
                            pass
                    default_edit_date = date.today() if edit_visited and existing_date is None else existing_date
                    edit_visited_date = st.date_input(
                        "Date Visited (optional)",
                        value=default_edit_date,
                        key=f"edit_visited_date_{global_idx}"
                    )
                    visited_date_edit = edit_visited_date if edit_visited_date is not None else None
                    st.markdown("### Add more photos")
                    new_images = st.file_uploader("Upload additional photos",
                                                  accept_multiple_files=True, key=f"edit_images_{global_idx}")
                    if r.get("images"):
                        st.markdown("### Current photos")
                        if images_to_delete_key not in st.session_state:
                            st.session_state[images_to_delete_key] = set()
                        cols = st.columns(3)
                        for i, img_url in enumerate(r["images"]):
                            with cols[i % 3]:
                                st.image(img_url, width="stretch")
                                if st.checkbox("Delete this photo", key=f"del_img_{global_idx}_{i}"):
                                    st.session_state[images_to_delete_key].add(img_url)
                    st.markdown("### Notes")
                    if reviews_key not in st.session_state:
                        st.session_state[reviews_key] = r["reviews"][:]
                    current_reviews = st.session_state[reviews_key]
                    for rev_idx, note in enumerate(current_reviews):
                        col1, col2 = st.columns([8, 1])
                        with col1:
                            new_note = st.text_area(
                                "Note",
                                value=note or "",
                                key=f"rev_comment_{global_idx}_{rev_idx}",
                                label_visibility="collapsed",
                                height=100
                            )
                        with col2:
                            if st.button("🗑️", key=f"del_rev_{global_idx}_{rev_idx}"):
                                st.session_state[reviews_key].pop(rev_idx)
                                st.rerun()
                        if new_note != note:
                            st.session_state[reviews_key][rev_idx] = new_note
                    st.markdown("**Add a new note**")
                    new_note_text = st.text_area("New note (optional)", height=100, key=f"new_note_{global_idx}")
                    if new_note_text.strip() and st.button("➕ Add Note", key=f"add_note_btn_{global_idx}"):
                        st.session_state[reviews_key].append(new_note_text.strip())
                        st.rerun()
                    if not current_reviews:
                        st.info("No notes yet.")
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 Save Changes", type="primary", use_container_width=True, key=f"save_{global_idx}"):
                            new_image_urls = []
                            if new_images:
                                with st.spinner("Uploading new images..."):
                                    new_image_urls = upload_images_to_supabase(new_images, edit_name)
                            remaining_images = r["images"][:]
                            if images_to_delete_key in st.session_state:
                                for url in list(st.session_state[images_to_delete_key]):
                                    if url in remaining_images:
                                        remaining_images.remove(url)
                                    # Delete from storage
                                    try:
                                        parsed = urllib.parse.urlparse(url)
                                        full_path = parsed.path.lstrip('/')
                                        prefix = f"storage/v1/object/public/{BUCKET_NAME}/"
                                        if full_path.startswith(prefix):
                                            file_path = full_path[len(prefix):]
                                            supabase.storage.from_(BUCKET_NAME).remove([file_path])
                                    except:
                                        pass
                            updated_date_str = visited_date_edit.strftime("%B %d, %Y") if visited_date_edit else None
                            cleaned_reviews = [n.strip() for n in st.session_state.get(reviews_key, r["reviews"]) if n and n.strip()]
                            new_lat, new_lon = r.get("latitude"), r.get("longitude")
                            if edit_address.strip() != r["address"]:
                                with st.spinner("Location changed. Updating coordinates..."):
                                    fetched_lat, fetched_lon = get_lat_lon(edit_address.strip())
                                    if fetched_lat:
                                        new_lat, new_lon = fetched_lat, fetched_lon
                                    else:
                                        st.warning("Could not map new address. Coordinates cleared.")
                                        new_lat, new_lon = None, None
                            restaurants[global_idx].update({
                                "name": edit_name.strip(),
                                "cuisine": edit_cuisine,
                                "price": edit_price,
                                "location": edit_location,
                                "address": edit_address.strip(),
                                "type": edit_type,
                                "visited": edit_visited,
                                "visited_date": updated_date_str,
                                "images": remaining_images + new_image_urls,
                                "reviews": cleaned_reviews,
                                "latitude": new_lat,
                                "longitude": new_lon,
                                "retired": edit_retired
                            })
                            save_data([restaurants[global_idx]])
                            del st.session_state[f"edit_mode_{global_idx}"]
                            if images_to_delete_key in st.session_state:
                                del st.session_state[images_to_delete_key]
                            if reviews_key in st.session_state:
                                del st.session_state[reviews_key]
                            st.session_state.success_message = "Changes saved!"
                            st.rerun()
                    with col_cancel:
                        if st.button("❌ Cancel", use_container_width=True, key=f"cancel_{global_idx}"):
                            del st.session_state[f"edit_mode_{global_idx}"]
                            if images_to_delete_key in st.session_state:
                                del st.session_state[images_to_delete_key]
                            if reviews_key in st.session_state:
                                del st.session_state[reviews_key]
                            st.rerun()
# ────────────────────────────── Map View ──────────────────────────────
elif action == "🗺️ Map View":
    st.header("Chicago Food Map 🗺️")
    carto_key = st.secrets.get("CARTO_API_KEY", "")
    if carto_key:
        tile_url = f"https://basemaps.cartocdn.com/rastertiles/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png?key={carto_key}"
        tile_attr = '© <a href="https://carto.com/attributions">CARTO</a>'
    else:
        st.warning("No CARTO_API_KEY found in secrets — falling back to a free basemap without a key.")
        tile_url = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        tile_attr = "Esri, HERE, Garmin, © OpenStreetMap contributors"
    m = folium.Map(location=[41.8781, -87.6298], zoom_start=12, tiles=tile_url, attr=tile_attr)
    LocateControl(auto_start=False, strings={"title": "Show me where I am", "popup": "You are here!"}).add_to(m)
    marker_cluster = MarkerCluster().add_to(m)
    legend_html = '''
    <div style="position: fixed; top: 10px; right: 10px; width: 130px; height: auto; max-height: 300px; overflow-y: auto;
                border: 1px solid #C9A034; z-index: 9999; font-size: 12px; font-family: 'Work Sans', sans-serif;
                background-color: #241F18; opacity: 0.95;
                padding: 0px; border-radius: 6px; color: #F1E9D8;">
        <details>
            <summary style="cursor: pointer; padding: 6px 8px; font-weight: 600; background-color: #2E271D; color: #E3C066; border-radius: 6px 6px 0 0;">Legend 🗺️</summary>
            <div style="padding: 8px;">
                <i class="fa fa-map-marker" style="color:#5B9BD5; font-size:14px;"></i> You<br>
                <i class="fa fa-map-marker" style="color:#6B8863; font-size:14px;"></i> Visited<br>
                <i class="fa fa-map-marker" style="color:#A79A85; font-size:14px;"></i> Not Visited<br>
                <hr style="margin: 5px 0; border-color: rgba(201,160,52,0.3);">
                🍽️ Restaurant<br>
                🍸 Cocktail Bar
            </div>
        </details>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    places_mapped = 0
    places_skipped = 0
    for r in restaurants:
        if r.get("retired", False):
            places_skipped += 1
            continue
        lat = r.get("latitude")
        lon = r.get("longitude")
        if lat is not None and lon is not None:
            places_mapped += 1
            color = "green" if r.get("visited") else "lightgray"
            icon_name = "glass" if r["type"] == "cocktail_bar" else "cutlery"
            icon_prefix = "glyphicon"
            image_html = ""
            if r.get("images"):
                image_html = f'<img src="{r["images"][0]}" style="width:100%; height:120px; object-fit:cover; border-radius:5px; margin-bottom:8px;">'
            html = f"""
            <div style="font-family: 'Work Sans', sans-serif; width: 200px; background-color: #241F18; color: #F1E9D8; padding: 6px; border-radius: 6px;">
                {image_html}
                <h4 style="font-family: 'Fraunces', serif; color: #E3C066; margin: 4px 0;">{r['name']}</h4>
                <p style="margin: 2px 0;"><b>{r['cuisine']}</b> • {r['price']}</p>
                <p style="margin: 2px 0; color: #A79A85;">{r['location']}</p>
                <a href="{google_maps_link(r.get('address',''), r['name'])}" target="_blank" style="color: #E3C066;">Open in Google Maps</a>
            </div>
            """
            folium.Marker(
                [lat, lon],
                popup=folium.Popup(html, max_width=250),
                tooltip=r["name"],
                icon=folium.Icon(color=color, icon=icon_name, prefix=icon_prefix)
            ).add_to(marker_cluster)
        else:
            places_skipped += 1
    st.caption(f"Showing {places_mapped} location(s).")
    if places_skipped > 0:
        st.caption(f"({places_skipped} places hidden due to missing coordinates or retired status)")
    st_folium(m, width="100%", height=600)
# ────────────────────────────── Add a Place ──────────────────────────────
elif action == "➕ Add a Place":
    st.header("Add a New Place 📍")
    if not st.session_state.is_admin:
        st.warning("🔒 Admin login required to add places. Use the Admin Login in the sidebar.")
        st.stop()

    name = st.text_input("Name*")

    address = st.text_input("Address*", key="add_address",
                            help="Neighborhood (and cuisine/type, when we can tell) fill in automatically once you enter this.")

    # ---------- Auto-fill triggered by the address ----------
    # Runs once per distinct address the user types (tracked via last_lookup_address),
    # not on every keystroke — Streamlit only reruns this when the field loses focus
    # or the user hits Enter, so this fires right after they finish typing it.
    clean_address = address.strip()
    if clean_address and clean_address != st.session_state.get("last_lookup_address"):
        with st.spinner("Looking up that address..."):
            found = lookup_place_by_address(clean_address)
        st.session_state.last_lookup_address = clean_address
        if found:
            guessed_cuisine, guessed_type = guess_cuisine_and_type(found.get("category"))
            guessed_neighborhood = guess_neighborhood(found["latitude"], found["longitude"])
            st.session_state.autofill = {
                "address": clean_address,
                "latitude": found["latitude"],
                "longitude": found["longitude"],
                "cuisine": guessed_cuisine,
                "location": guessed_neighborhood,
                "type": guessed_type,
            }
            st.rerun()
        else:
            st.session_state.autofill = {}
            st.warning("⚠️ Couldn't locate that address — you can still fill in the fields below by hand.")

    autofill = st.session_state.get("autofill", {})
    if autofill.get("address") == clean_address and autofill.get("latitude"):
        st.caption("📍 Neighborhood (and cuisine/type, if recognized) filled in below from the address — adjust anything that's off.")

    cuisine_default = autofill.get("cuisine", CUISINES[0])
    cuisine = st.selectbox("Cuisine/Style*", CUISINES,
                           index=CUISINES.index(cuisine_default) if cuisine_default in CUISINES else 0)
    price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"])
    location_default = autofill.get("location", NEIGHBORHOODS[0])
    location = st.selectbox("Neighborhood*", NEIGHBORHOODS,
                            index=NEIGHBORHOODS.index(location_default) if location_default in NEIGHBORHOODS else 0)
    place_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"],
                              index=0 if autofill.get("type", "restaurant") == "restaurant" else 1,
                              format_func=lambda x: "Restaurant 🍽️" if x == "restaurant" else "Cocktail Bar 🍸")
    retired = st.checkbox("😔 Retired?", False)
    visited = st.checkbox("✅ I've already visited this place")
    default_date = date.today() if visited else None
    visited_date = st.date_input("Date Visited", value=default_date) if visited else None
    uploaded_images = st.file_uploader("Upload photos", accept_multiple_files=True)
    quick_notes = st.text_area("Quick notes (optional)", height=100)
    if st.button("Add Place", type="primary"):
        if not all([name.strip(), address.strip()]):
            st.error("Name and address required")
        elif any(r["name"].lower() == name.lower().strip() for r in restaurants):
            st.warning("Already exists!")
        else:
            # Reuse the coordinates from the address auto-fill lookup if the
            # address wasn't hand-edited afterward, so we don't geocode twice.
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
                    image_urls = upload_images_to_supabase(uploaded_images, name)
            visited_date_str = visited_date.strftime("%B %d, %Y") if visited_date else None
            new_reviews = [quick_notes.strip()] if quick_notes.strip() else []
            new = {
                "name": name.strip(),
                "cuisine": cuisine,
                "price": price,
                "location": location,
                "address": address.strip(),
                "type": place_type,
                "favorite": False,
                "visited": visited,
                "visited_date": visited_date_str,
                "reviews": new_reviews,
                "images": image_urls,
                "latitude": lat,
                "longitude": lon,
                "retired": retired
            }
            inserted = save_data([new])
            if inserted:
                restaurants.append(inserted)
                if "autofill" in st.session_state:
                    del st.session_state.autofill
                if "last_lookup_address" in st.session_state:
                    del st.session_state.last_lookup_address
                st.session_state.success_message = f"{name} added successfully!"
                st.rerun()
            else:
                st.error("Failed to add place.")
# ────────────────────────────── Random Pick ──────────────────────────────
else:
    st.header("Random Place Picker 🎲")
    if not restaurants:
        st.info("Add places first!")
    else:
        with st.container(border=True):
            st.markdown("### 🕵️ Filter Options")
            c1, c2, c3 = st.columns(3)
            with c1:
                cuisine_filter = st.multiselect("Cuisine", sorted({r["cuisine"] for r in restaurants}))
            with c2:
                location_filter = st.multiselect("Neighborhood", sorted({r["location"] for r in restaurants}))
            with c3:
                price_filter = st.multiselect("Price", sorted({r["price"] for r in restaurants}, key=len))
            c4, c5, c6 = st.columns(3)
            with c4:
                type_filter = st.selectbox("Type", ["all", "restaurant", "cocktail_bar"],
                                           format_func=lambda x: {"all": "All", "restaurant": "Restaurants 🍽️", "cocktail_bar": "Bars 🍸"}[x])
            with c5:
                visited_filter = st.selectbox("Visited Status", VISITED_OPTIONS)
            with c6:
                pass
            c7, c8, c9 = st.columns(3)
            with c7:
                include_retired = st.checkbox("😔 Include Retired?", False)
            with c8:
                only_fav = st.checkbox("❤️ Favorites only")
            with c9:
                pass
        filtered = [
            r for r in restaurants
            if (not only_fav or r.get("favorite"))
            and (type_filter == "all" or r.get("type") == type_filter)
            and (not cuisine_filter or r["cuisine"] in cuisine_filter)
            and (not price_filter or r["price"] in price_filter)
            and (not location_filter or r["location"] in location_filter)
            and (visited_filter == "All" or
                 (visited_filter == "Visited Only" and r.get("visited")) or
                 (visited_filter == "Not Visited Yet" and not r.get("visited")))
            and (include_retired or not r.get("retired", False))
        ]
        st.caption(f"**{len(filtered)} places** match your filters")
        if not filtered:
            st.warning("No matches – try broader filters!")
        else:
            if st.button("🎲 Pick Random Place!", type="primary", use_container_width=True):
                placeholder = st.empty()
                run_spin(placeholder, filtered, SPIN_SCHEDULE_MAIN)
                picked = random.choice(filtered)
                st.session_state.last_pick = picked
                st.rerun()
            if "last_pick" in st.session_state:
                c = st.session_state.last_pick
                if c in filtered:
                    st.markdown("---")
                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div class="ticket">
                                <div class="ticket-eyebrow">Tonight's Pick</div>
                                <h1>{c['name']}</h1>
                                <div class="ticket-stamp">Selected</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        render_badges(c)
                        idx = restaurants.index(c)
                        if st.session_state.is_admin:
                            col_fav, col_vis = st.columns(2)
                            with col_fav:
                                if st.button("❤️ Unfavorite" if c.get("favorite") else "❤️ Favorite",
                                             key=f"rand_fav_{idx}", use_container_width=True):
                                    toggle_favorite(idx)
                            with col_vis:
                                if st.button("✅ Mark as Unvisited" if c.get("visited") else "✅ Mark as Visited",
                                             key=f"rand_vis_{idx}", type="secondary", use_container_width=True):
                                    toggle_visited(idx)
                        st.markdown("---")
                        st.write(f"📍 **Address:** {c.get('address','')}")
                        st.markdown(f"[🗺️ Open in Google Maps]({google_maps_link(c.get('address',''), c['name'])})", unsafe_allow_html=True)
                        if c["reviews"]:
                            st.markdown("### 📝 Notes")
                            for note in c["reviews"]:
                                if note and str(note).strip():
                                    with st.container(border=True):
                                        st.write(str(note).strip())
                        else:
                            st.info("No notes yet!")
                        if c.get("images"):
                            st.markdown("### 📸 Photos")
                            cols = st.columns(3)
                            for i, img_url in enumerate(c["images"]):
                                with cols[i % 3]:
                                    st.image(img_url, width="stretch")
                        st.markdown("---")
                        if st.button("🎲 Pick Again (from same filters)", type="secondary", use_container_width=True):
                            placeholder = st.empty()
                            run_spin(placeholder, filtered, SPIN_SCHEDULE_AGAIN)
                            picked = random.choice(filtered)
                            st.session_state.last_pick = picked
                            st.rerun()
                else:
                    st.info("Previous pick no longer matches current filters — pick again!")
