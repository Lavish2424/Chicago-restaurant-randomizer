import streamlit as st
import random
import urllib.parse
from datetime import datetime, date
from supabase import create_client, Client
import os
import uuid
from streamlit_folium import st_folium
import folium
from geopy.geocoders import ArcGIS
import time
from folium.plugins import LocateControl, MarkerCluster

# ==================== SUPABASE SETUP ====================
try:
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_ANON_KEY"]
except (FileNotFoundError, KeyError):
    st.error("Secrets not found. Please set up your .streamlit/secrets.toml file.")
    st.stop()

supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"
geolocator = ArcGIS(timeout=10)

# ==================== DATA & CACHING ====================

@st.cache_data(ttl=300)  # Cache data for 5 minutes
def fetch_restaurants_from_db():
    """Direct fetch from Supabase."""
    try:
        response = supabase.table("restaurants").select("*").execute()
        data = response.data
        for place in data:
            # Ensure all keys exist to prevent KeyErrors
            place.setdefault("favorite", False)
            place.setdefault("visited", False)
            place.setdefault("visited_date", None)
            place.setdefault("reviews", [])
            place.setdefault("images", [])
            place.setdefault("latitude", None)
            place.setdefault("longitude", None)
        return data
    except Exception as e:
        st.error(f"Database Error: {e}")
        return []

def refresh_app_data():
    """Clears cache and forces a reload from the DB."""
    st.cache_data.clear()
    st.session_state.restaurants = fetch_restaurants_from_db()

# ==================== HELPER FUNCTIONS ====================

def get_lat_lon(address):
    """Converts an address string to latitude and longitude using ArcGIS."""
    try:
        clean_addr = address.strip()
        if not clean_addr: return None, None
        
        search_query = clean_addr if any(x in clean_addr.lower() for x in ["chicago", "il"]) else f"{clean_addr}, Chicago, IL"
        location = geolocator.geocode(search_query)
        return (location.latitude, location.longitude) if location else (None, None)
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None

def upsert_restaurant(place_data):
    """Updates one restaurant or inserts a new one."""
    try:
        # Clean the data payload
        payload = {k: v for k, v in place_data.items() if k != "id"}
        
        if "id" in place_data and place_data["id"]:
            supabase.table("restaurants").update(payload).eq("id", place_data["id"]).execute()
        else:
            supabase.table("restaurants").insert(payload).execute()
        
        refresh_app_data()
    except Exception as e:
        st.error(f"Error saving to database: {str(e)}")

def delete_restaurant(index):
    r = st.session_state.restaurants[index]
    if r.get("images"):
        # Logic to extract paths and remove from storage
        paths = []
        for url in r["images"]:
            try:
                path = urllib.parse.urlparse(url).path
                prefix = f"/storage/v1/object/public/{BUCKET_NAME}/"
                if path.startswith(prefix): paths.append(path[len(prefix):])
            except: pass
        if paths:
            try: supabase.storage.from_(BUCKET_NAME).remove(paths)
            except: pass
            
    if "id" in r:
        supabase.table("restaurants").delete().eq("id", r["id"]).execute()
    
    refresh_app_data()
    st.success(f"{r['name']} deleted!")
    st.rerun()

def upload_images_to_supabase(uploaded_files, restaurant_name):
    urls = []
    sanitized_name = "".join(c for c in restaurant_name if c.isalnum() or c in " -_").rstrip()
    for i, file in enumerate(uploaded_files):
        try:
            file_ext = os.path.splitext(file.name)[1].lower()
            unique_id = str(uuid.uuid4())[:8] # Prevents CDN/Browser caching issues
            file_path = f"{sanitized_name}/{sanitized_name}_{unique_id}_{i}{file_ext}"
            
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path,
                file=file.getvalue(),
                file_options={"content-type": file.type, "upsert": "true"}
            )
            urls.append(supabase.storage.from_(BUCKET_NAME).get_public_url(file_path))
        except Exception as e:
            st.error(f"Failed to upload {file.name}: {str(e)}")
    return urls

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

# ==================== APP LOGIC ====================

# Initialize State
if "restaurants" not in st.session_state:
    st.session_state.restaurants = fetch_restaurants_from_db()
restaurants = st.session_state.restaurants

st.markdown("<h1 style='text-align: center;'>🍽️🍸 Chicago Restaurant Randomizer</h1>", unsafe_allow_html=True)

st.sidebar.header("Actions")
action = st.sidebar.radio("Navigation", ["View All Places", "Map View", "Add a Place", "Random Pick"])

# Clear temporary edit states on navigation
if "previous_action" not in st.session_state or st.session_state.previous_action != action:
    keys_to_clear = [k for k in st.session_state.keys() if any(x in k for x in ["edit_mode_", "del_confirm_", "last_pick"])]
    for k in keys_to_clear: del st.session_state[k]
    st.session_state.previous_action = action

NEIGHBORHOODS = ["Fulton Market", "River North", "Gold Coast", "South Loop", "Chinatown", "Pilsen", "West Town", "West Loop", "Lincoln Park", "Wicker Park", "Logan Square"]
CUISINES = ["American", "Asian", "Mexican", "Japanese", "Italian", "Indian", "Thai", "French", "Seafood", "Steakhouse", "Cocktails", "Other"]

# ────────────────────────────── View All Places ──────────────────────────────
if action == "View All Places":
    st.header("All Places 👀")
    
    col_search, col_sort = st.columns([5, 3])
    search_term = col_search.text_input("🔍 Search", placeholder="Name, neighborhood, or cuisine...")
    sort_option = col_sort.selectbox("Sort by", ["A-Z (Name)", "Favorites First", "Recently Added"])

    filtered = restaurants.copy()
    if search_term:
        term = search_term.lower()
        filtered = [r for r in filtered if term in r["name"].lower() or term in r["cuisine"].lower() or term in r["location"].lower()]

    # Sorting
    if sort_option == "A-Z (Name)":
        filtered.sort(key=lambda x: x["name"].lower())
    elif sort_option == "Favorites First":
        filtered.sort(key=lambda x: x.get("favorite", False), reverse=True)
    elif sort_option == "Recently Added":
        filtered.sort(key=lambda x: x.get("id", 0), reverse=True)

    for idx, r in enumerate(filtered):
        # We need the original index for state management if not using IDs
        # But using ID from DB is safer
        r_id = r.get("id")
        with st.expander(f"{'❤️ ' if r.get('favorite') else ''}{r['name']} — {r['location']} ({r['cuisine']})"):
            
            if f"edit_mode_{r_id}" not in st.session_state:
                # DISPLAY MODE
                c1, c2, c3, c4 = st.columns(4)
                if c1.button("❤️" if not r.get("favorite") else "💔", key=f"fav_{r_id}"):
                    r["favorite"] = not r.get("favorite")
                    upsert_restaurant(r)
                    st.rerun()
                
                if c2.button("✅" if not r.get("visited") else "❓", key=f"vis_{r_id}"):
                    r["visited"] = not r.get("visited")
                    r["visited_date"] = date.today().strftime("%B %d, %Y") if r["visited"] else None
                    upsert_restaurant(r)
                    st.rerun()

                if c3.button("Edit ✏️", key=f"ed_{r_id}"):
                    st.session_state[f"edit_mode_{r_id}"] = True
                    st.rerun()

                if c4.button("Delete 🗑️", key=f"del_{r_id}"):
                    delete_restaurant(restaurants.index(r))
                
                st.write(f"**📍 Address:** {r['address']}")
                st.write(f"**💰 Price:** {r['price']}")
                if r.get("visited_date"): st.caption(f"Visited on: {r['visited_date']}")
                
                if r.get("reviews"):
                    st.info("\n\n".join(r["reviews"]))
                
                if r.get("images"):
                    cols = st.columns(3)
                    for i, img in enumerate(r["images"]):
                        cols[i % 3].image(img, use_container_width=True)
            else:
                # EDIT MODE
                with st.form(f"form_{r_id}"):
                    new_name = st.text_input("Name", value=r["name"])
                    new_addr = st.text_input("Address", value=r["address"])
                    new_notes = st.text_area("Notes", value="\n".join(r["reviews"]))
                    
                    if st.form_submit_button("Save Changes"):
                        r["name"] = new_name
                        # Only re-geocode if address changed
                        if new_addr != r["address"]:
                            lat, lon = get_lat_lon(new_addr)
                            r["latitude"], r["longitude"] = lat, lon
                        r["address"] = new_addr
                        r["reviews"] = [new_notes.strip()] if new_notes.strip() else []
                        upsert_restaurant(r)
                        del st.session_state[f"edit_mode_{r_id}"]
                        st.rerun()
                if st.button("Cancel", key=f"can_{r_id}"):
                    del st.session_state[f"edit_mode_{r_id}"]
                    st.rerun()

# ────────────────────────────── Map View ──────────────────────────────
elif action == "Map View":
    st.header("Chicago Food Map 🗺️")
    m = folium.Map(location=[41.8781, -87.6298], zoom_start=12)
    marker_cluster = MarkerCluster().add_to(m)
    LocateControl().add_to(m)

    for r in restaurants:
        if r.get("latitude") and r.get("longitude"):
            color = "green" if r.get("visited") else "blue"
            icon = "glass" if r["type"] == "cocktail_bar" else "cutlery"
            
            html = f"<b>{r['name']}</b><br>{r['cuisine']}<br><a href='{google_maps_link(r['address'])}' target='_blank'>Directions</a>"
            folium.Marker(
                [r["latitude"], r["longitude"]],
                popup=folium.Popup(html, max_width=200),
                icon=folium.Icon(color=color, icon=icon)
            ).add_to(marker_cluster)

    st_folium(m, width=700, height=500)

# ────────────────────────────── Add a Place ──────────────────────────────
elif action == "Add a Place":
    st.header("Add a New Place 📍")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Name*")
        address = st.text_input("Address*")
        cuisine = st.selectbox("Cuisine", CUISINES)
        price = st.select_slider("Price", options=["$", "$$", "$$$", "$$$$"])
        location = st.selectbox("Neighborhood", NEIGHBORHOODS)
        p_type = st.radio("Type", ["restaurant", "cocktail_bar"])
        imgs = st.file_uploader("Photos", accept_multiple_files=True)
        notes = st.text_area("Initial Notes")
        
        if st.form_submit_button("Add to List"):
            if name and address:
                with st.spinner("Geocoding and uploading..."):
                    lat, lon = get_lat_lon(address)
                    img_urls = upload_images_to_supabase(imgs, name) if imgs else []
                    
                    new_place = {
                        "name": name,
                        "address": address,
                        "cuisine": cuisine,
                        "price": price,
                        "location": location,
                        "type": p_type,
                        "latitude": lat,
                        "longitude": lon,
                        "images": img_urls,
                        "reviews": [notes] if notes else [],
                        "favorite": False,
                        "visited": False
                    }
                    upsert_restaurant(new_place)
                    st.success("Added!")
                    st.rerun()
            else:
                st.error("Name and Address are required.")

# ────────────────────────────── Random Pick ──────────────────────────────
else:
    st.header("Random Picker 🎲")
    if not restaurants:
        st.warning("No restaurants found.")
    else:
        if st.button("Pick a Place!", type="primary"):
            # Filtering can be added here
            pick = random.choice(restaurants)
            st.session_state.last_pick = pick
        
        if "last_pick" in st.session_state:
            p = st.session_state.last_pick
            st.balloons()
            st.markdown(f"## 🎯 You should go to: **{p['name']}**")
            st.write(f"It's a {p['cuisine']} spot in {p['location']}.")
            if st.button("Open in Maps"):
                st.write(f"Link: {google_maps_link(p['address'], p['name'])}")
