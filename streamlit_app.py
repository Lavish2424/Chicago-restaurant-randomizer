import streamlit as st
import random
import urllib.parse
from datetime import datetime, date
from supabase import create_client, Client
import os
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# ==================== SUPABASE SETUP ====================
# Ensure these are set in your .streamlit/secrets.toml
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"

# Geocoder setup
geolocator = Nominatim(user_agent="chicago_restaurant_app")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# ==================== HELPER FUNCTIONS ====================

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
            place.setdefault("lat", None)
            place.setdefault("lon", None)
        return data
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return []

def save_data(data):
    """Saves the entire state to Supabase."""
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
                "lat": place.get("lat"),
                "lon": place.get("lon")
            }
            if place_id:
                supabase.table("restaurants").update(update_data).eq("id", place_id).execute()
            else:
                supabase.table("restaurants").insert(update_data).execute()
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")

def delete_restaurant(index):
    r = st.session_state.restaurants[index]
    if r.get("images"):
        paths_to_delete = []
        for url in r["images"]:
            try:
                parsed = urllib.parse.urlparse(url)
                path = parsed.path
                prefix = f"/storage/v1/object/public/{BUCKET_NAME}/"
                if path.startswith(prefix):
                    file_path = path[len(prefix):]
                    paths_to_delete.append(file_path)
            except:
                pass
        if paths_to_delete:
            try:
                supabase.storage.from_(BUCKET_NAME).remove(paths_to_delete)
            except:
                pass
    if "id" in r:
        supabase.table("restaurants").delete().eq("id", r["id"]).execute()
    
    st.session_state.restaurants = load_data()
    st.success(f"{r['name']} deleted!")
    st.rerun()

def toggle_favorite(idx):
    st.session_state.restaurants[idx]["favorite"] = not st.session_state.restaurants[idx].get("favorite", False)
    save_data(st.session_state.restaurants)
    st.session_state.restaurants = load_data()
    st.rerun()

def toggle_visited(idx):
    st.session_state.restaurants[idx]["visited"] = not st.session_state.restaurants[idx].get("visited", False)
    # If marking unvisited, clear the date
    if not st.session_state.restaurants[idx]["visited"]:
        st.session_state.restaurants[idx]["visited_date"] = None
    save_data(st.session_state.restaurants)
    st.session_state.restaurants = load_data()
    st.rerun()

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

def upload_images_to_supabase(uploaded_files, restaurant_name):
    urls = []
    sanitized_name = "".join(c for c in restaurant_name if c.isalnum() or c in " -_").rstrip()
    for i, file in enumerate(uploaded_files):
        try:
            file_ext = os.path.splitext(file.name)[1].lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{sanitized_name}_{timestamp}_{i}{file_ext}"
            file_path = f"{sanitized_name}/{filename}"
            
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_path,
                file=file.getvalue(),
                file_options={"content-type": file.type, "upsert": "true"}
            )
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            urls.append(public_url)
        except Exception as e:
            st.error(f"Failed to upload {file.name}: {str(e)}")
    return urls

# ==================== SESSION STATE ====================

if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

# ==================== UI SETUP ====================

st.markdown("<h1 style='text-align: center;'>🍽️🍸 Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?", ["View All Places", "Add a Place", "Random Pick", "Map"])

# Reset temporary states on tab change
if "previous_action" not in st.session_state:
    st.session_state.previous_action = action

if st.session_state.previous_action != action:
    if "last_pick" in st.session_state:
        del st.session_state.last_pick
    keys_to_clear = [k for k in st.session_state.keys() if k.startswith("edit_mode_") or k.startswith("images_to_delete_") or k.startswith("del_confirm_")]
    for k in keys_to_clear:
        del st.session_state[k]
    st.session_state.previous_action = action

st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")

NEIGHBORHOODS = ["Fulton Market", "River North", "Gold Coast", "South Loop", "Chinatown", "Pilsen", "West Town", "West Loop", "Wicker Park", "Logan Square", "Old Town", "Lincoln Park"]
CUISINES = ["American", "Asian", "Mexican", "Japanese", "Italian", "Indian", "Thai", "French", "Seafood", "Steakhouse", "Cocktails", "Other"]
VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]

# ==================== VIEW ALL PLACES ====================
if action == "View All Places":
    st.header("All Places 👀")
    restaurants = st.session_state.restaurants
    st.caption(f"{len(restaurants)} place(s)")
    
    if not restaurants:
        st.info("No places added yet.")
    else:
        col_search, col_sort = st.columns([5, 3])
        with col_search:
            search_term = st.text_input("🔍 Search name, cuisine, neighborhood", key="search_input")
        with col_sort:
            sort_option = st.selectbox("Sort by", ["A-Z (Name)", "Favorites First", "Recently Added"])

        filtered = restaurants.copy()
        if search_term:
            lower = search_term.lower()
            filtered = [r for r in filtered if lower in r["name"].lower() or lower in r["cuisine"].lower() or lower in r["location"].lower()]

        for idx, r in enumerate(filtered):
            # Find the global index in session state for accurate updates
            global_idx = next(i for i, res in enumerate(st.session_state.restaurants) if res.get('id') == r.get('id'))
            
            icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
            fav = " ❤️" if r.get("favorite") else ""
            visited = " ✅" if r.get("visited") else ""
            visited_date_str = f" (visited {r['visited_date']})" if r.get("visited") and r.get("visited_date") else ""
            
            with st.expander(f"{r['name']}{icon}{fav}{visited}{visited_date_str} • {r['location']}", expanded=(f"edit_mode_{global_idx}" in st.session_state)):
                if f"edit_mode_{global_idx}" not in st.session_state:
                    # --- DISPLAY MODE ---
                    b1, b2, b3, b4 = st.columns(4)
                    with b1:
                        if st.button("❤️" if not r.get("favorite") else "💔", key=f"fav_{global_idx}", use_container_width=True):
                            toggle_favorite(global_idx)
                    with b2:
                        if st.button("✅" if not r.get("visited") else "❌", key=f"vis_{global_idx}", use_container_width=True):
                            toggle_visited(global_idx)
                    with b3:
                        if st.button("Edit ✏️", key=f"edit_btn_{global_idx}", use_container_width=True):
                            st.session_state[f"edit_mode_{global_idx}"] = True
                            st.rerun()
                    with b4:
                        if st.button("Delete 🗑️", key=f"del_btn_{global_idx}", use_container_width=True):
                            delete_restaurant(global_idx)

                    st.write(f"**Cuisine:** {r['cuisine']} | **Price:** {r['price']}")
                    st.write(f"**Address:** {r.get('address', 'N/A')}")
                    st.markdown(f"[📍 Open in Google Maps]({google_maps_link(r.get('address', ''), r['name'])})")
                    
                    if r.get("images"):
                        st.write("**Photos:**")
                        cols = st.columns(3)
                        for i, img in enumerate(r["images"]):
                            cols[i % 3].image(img, use_column_width=True)
                else:
                    # --- EDIT MODE ---
                    st.subheader(f"Editing: {r['name']}")
                    edit_name = st.text_input("Name", value=r["name"], key=f"en_{global_idx}")
                    edit_addr = st.text_input("Address", value=r.get("address", ""), key=f"ea_{global_idx}")
                    edit_loc = st.selectbox("Neighborhood", NEIGHBORHOODS, index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else 0, key=f"el_{global_idx}")
                    
                    # DATE PICKER FIX: value=None allows it to be blank
                    existing_date = None
                    if r.get("visited_date"):
                        try:
                            existing_date = datetime.strptime(r["visited_date"], "%B %d, %Y").date()
                        except:
                            existing_date = None
                    
                    edit_visited_date = st.date_input(
                        "Date Visited (Optional)",
                        value=existing_date,
                        key=f"edate_{global_idx}"
                    )

                    c_save, c_cancel = st.columns(2)
                    with c_save:
                        if st.button("💾 Save", key=f"sv_{global_idx}", type="primary"):
                            formatted_date = edit_visited_date.strftime("%B %d, %Y") if edit_visited_date else None
                            st.session_state.restaurants[global_idx].update({
                                "name": edit_name,
                                "address": edit_addr,
                                "location": edit_loc,
                                "visited_date": formatted_date,
                                "visited": True if formatted_date else r.get("visited", False)
                            })
                            save_data(st.session_state.restaurants)
                            del st.session_state[f"edit_mode_{global_idx}"]
                            st.rerun()
                    with c_cancel:
                        if st.button("Cancel", key=f"cn_{global_idx}"):
                            del st.session_state[f"edit_mode_{global_idx}"]
                            st.rerun()

# ==================== ADD A PLACE ====================
elif action == "Add a Place":
    st.header("Add a New Place 📍")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Name*")
        address = st.text_input("Address*")
        cuisine = st.selectbox("Cuisine*", CUISINES)
        price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"])
        location = st.selectbox("Neighborhood*", NEIGHBORHOODS)
        place_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"])
        
        # DATE PICKER FIX: value=None makes it blank by default
        visited_date_input = st.date_input("Date Visited (leave blank if not visited)", value=None)
        
        uploaded_images = st.file_uploader("Upload photos", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        
        submitted = st.form_submit_button("Add Place", type="primary")
        if submitted:
            if name and address:
                with st.spinner("Saving..."):
                    img_urls = upload_images_to_supabase(uploaded_images, name) if uploaded_images else []
                    
                    # Geocoding
                    full_addr = f"{address}, Chicago, IL"
                    geo = geocode(full_addr)
                    lat, lon = (geo.latitude, geo.longitude) if geo else (None, None)
                    
                    v_date_str = visited_date_input.strftime("%B %d, %Y") if visited_date_input else None
                    
                    new_place = {
                        "name": name,
                        "address": address,
                        "cuisine": cuisine,
                        "price": price,
                        "location": location,
                        "type": place_type,
                        "visited": True if v_date_str else False,
                        "visited_date": v_date_str,
                        "images": img_urls,
                        "lat": lat,
                        "lon": lon,
                        "reviews": []
                    }
                    supabase.table("restaurants").insert(new_place).execute()
                    st.session_state.restaurants = load_data()
                    st.success(f"Added {name}!")
                    st.rerun()
            else:
                st.error("Name and Address are required!")

# ==================== MAP ====================
elif action == "Map":
    st.header("Chicago Food Map 🗺️")
    places = [r for r in st.session_state.restaurants if r.get("lat") and r.get("lon")]
    if not places:
        st.info("No places with locations yet.")
    else:
        m = folium.Map(location=[41.8781, -87.6298], zoom_start=12)
        for p in places:
            color = "red" if p.get("visited") else "blue"
            folium.Marker(
                [p["lat"], p["lon"]],
                popup=f"<b>{p['name']}</b><br>{p['cuisine']}",
                tooltip=p["name"],
                icon=folium.Icon(color=color, icon="cutlery", prefix="fa")
            ).add_to(m)
        st_folium(m, width=700, height=500)

# ==================== RANDOM PICK ====================
else:
    st.header("Random Picker 🎲")
    if not st.session_state.restaurants:
        st.info("Add some places first!")
    else:
        if st.button("🎲 Pick a Place!", use_container_width=True, type="primary"):
            st.session_state.last_pick = random.choice(st.session_state.restaurants)
        
        if "last_pick" in st.session_state:
            p = st.session_state.last_pick
            st.markdown(f"## {p['name']}")
            st.write(f"**{p['cuisine']}** in **{p['location']}** ({p['price']})")
            st.markdown(f"[📍 Open in Google Maps]({google_maps_link(p.get('address',''), p['name'])})")
