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

# ==================== CONFIG & SETUP ====================
st.set_page_config(page_title="Chicago Eats", page_icon="🍽️", layout="wide")

BUCKET_NAME = "restaurant-images"

# 1. Initialize Supabase (Cached Resource)
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        return create_client(url, key)
    except FileNotFoundError:
        st.error("Secrets not found. Please set up your .streamlit/secrets.toml file.")
        st.stop()
    except Exception as e:
        st.error(f"Supabase connection error: {e}")
        st.stop()

supabase = init_supabase()

# 2. Initialize Geocoder (Cached Resource)
@st.cache_resource
def init_geocoder():
    # If you have credentials in secrets, use them:
    # return ArcGIS(username=st.secrets.get("ARCGIS_USERNAME"), password=st.secrets.get("ARCGIS_PASSWORD"), timeout=10)
    return ArcGIS(timeout=10)

geolocator = init_geocoder()

# ==================== HELPER FUNCTIONS ====================

@st.cache_data(ttl=3600, show_spinner=False)
def get_lat_lon(address):
    """
    Converts address to lat/lon. Cached for 1 hour to prevent API throttling.
    """
    try:
        clean_addr = address.strip()
        if not clean_addr:
            return None, None
        
        # Contextualize for Chicago if not specified
        if "chicago" not in clean_addr.lower() and "il" not in clean_addr.lower():
            search_query = f"{clean_addr}, Chicago, IL"
        else:
            search_query = clean_addr
        
        # Small delay to be polite to the API
        time.sleep(0.5) 
        location = geolocator.geocode(search_query)
        
        if location:
            return location.latitude, location.longitude
        return None, None

    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None

def load_data():
    """Fetch all data from Supabase."""
    try:
        response = supabase.table("restaurants").select("*").execute()
        data = response.data
        # Normalize fields
        for place in data:
            place.setdefault("favorite", False)
            place.setdefault("visited", False)
            place.setdefault("visited_date", None)
            place.setdefault("reviews", [])
            place.setdefault("images", [])
            place.setdefault("latitude", None)
            place.setdefault("longitude", None)
            
            # Normalize reviews to strings
            normalized_reviews = []
            for rev in place.get("reviews", []):
                if isinstance(rev, dict) and "comment" in rev:
                    normalized_reviews.append(str(rev["comment"]).strip())
                elif isinstance(rev, str) and rev.strip():
                    normalized_reviews.append(rev.strip())
            place["reviews"] = normalized_reviews
        return data
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return []

def save_data(data_list, is_insert=False):
    """
    Saves a list of restaurant dicts. 
    If is_insert=True, it inserts and returns the new record with ID.
    If is_insert=False, it updates existing records based on ID.
    """
    try:
        results = []
        for place in data_list:
            update_payload = {
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
                "longitude": place.get("longitude")
            }

            if is_insert:
                # Insert
                response = supabase.table("restaurants").insert(update_payload).execute()
                if response.data:
                    results.append(response.data[0])
            else:
                # Update
                if place.get("id"):
                    supabase.table("restaurants").update(update_payload).eq("id", place["id"]).execute()
                    results.append(place)
        
        return results if is_insert else None

    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return None

def upload_images_to_supabase(uploaded_files, restaurant_name):
    urls = []
    # Sanitize name for folder creation
    sanitized_name = "".join(c for c in restaurant_name if c.isalnum() or c in " -_").rstrip()
    
    for i, file in enumerate(uploaded_files):
        try:
            timestamp = int(time.time())
            file_ext = os.path.splitext(file.name)[1].lower()
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

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

# ==================== APP STATE & UI ====================

if "restaurants" not in st.session_state:
    with st.spinner("Loading your spots..."):
        st.session_state.restaurants = load_data()
restaurants = st.session_state.restaurants

st.markdown("<h1 style='text-align: center;'>🍽️🍸 Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Your personal Chicago food & drink tracker</p>", unsafe_allow_html=True)

# Sidebar
st.sidebar.header("Navigation")
action = st.sidebar.radio("Go to:", ["View All Places", "Map View", "Add a Place", "Random Pick"])

# Clear editing state when switching tabs
if "previous_action" not in st.session_state:
    st.session_state.previous_action = action

if st.session_state.previous_action != action:
    # Clear specific session keys related to editing
    keys_to_clear = [k for k in st.session_state.keys() if any(x in k for x in ["edit_mode_", "images_to_delete_", "del_confirm_", "last_pick"])]
    for k in keys_to_clear:
        del st.session_state[k]
    st.session_state.previous_action = action

st.sidebar.markdown("---")
st.sidebar.caption(f"Total Places: **{len(restaurants)}**")

# Constants
NEIGHBORHOODS = ["Fulton Market", "River North", "Gold Coast", "South Loop", "Chinatown", "Pilsen", "West Town", "West Loop", "Lincoln Park", "Wicker Park", "Logan Square", "Lakeview", "Loop", "Other"]
CUISINES = ["American", "Asian", "Mexican", "Japanese", "Italian", "Indian", "Thai", "French", "Seafood", "Steakhouse", "Cocktails", "Pizza", "Other"]

# ────────────────────────────── View All Places ──────────────────────────────
if action == "View All Places":
    col_search, col_sort = st.columns([5, 2])
    with col_search:
        search_term = st.text_input("🔍 Search", placeholder="Name, cuisine, or neighborhood")
    with col_sort:
        sort_option = st.selectbox("Sort by", ["A-Z", "Favorites First", "Newest", "Oldest"])

    # Filtering
    filtered = restaurants.copy()
    if search_term:
        term = search_term.lower()
        filtered = [r for r in filtered if term in r["name"].lower() or term in r["cuisine"].lower() or term in r["location"].lower()]

    # Sorting
    if sort_option == "A-Z":
        filtered.sort(key=lambda x: x["name"].lower())
    elif sort_option == "Favorites First":
        filtered.sort(key=lambda x: (not x.get("favorite"), x["name"].lower()))
    elif sort_option == "Newest":
        filtered.sort(key=lambda x: x.get("id", 0), reverse=True)
    elif sort_option == "Oldest":
        filtered.sort(key=lambda x: x.get("id", 0))

    if not filtered:
        st.info("No places found.")

    for r in filtered:
        # Determine global index for state manipulation
        global_idx = restaurants.index(r)
        
        # Card Header Construction
        icon = "🍸" if r.get("type") == "cocktail_bar" else "🍽️"
        fav_icon = "❤️" if r.get("favorite") else ""
        visit_icon = "✅" if r.get("visited") else ""
        header_text = f"{icon} {r['name']} {fav_icon} {visit_icon}"
        sub_text = f"{r['cuisine']} • {r['price']} • {r['location']}"
        
        with st.expander(f"**{header_text}** \n_{sub_text}_", expanded=(f"edit_mode_{global_idx}" in st.session_state)):
            
            # --- VIEW MODE ---
            if f"edit_mode_{global_idx}" not in st.session_state:
                # Action Buttons
                c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
                
                # Toggle Favorite
                if c1.button("❤️ Fav" if not r.get("favorite") else "💔 Unfav", key=f"fav_{global_idx}", use_container_width=True):
                    restaurants[global_idx]["favorite"] = not restaurants[global_idx].get("favorite")
                    save_data([restaurants[global_idx]])
                    st.rerun()

                # Toggle Visited
                if c2.button("✅ Visited" if not r.get("visited") else "❌ Unvisit", key=f"vis_{global_idx}", use_container_width=True):
                    restaurants[global_idx]["visited"] = not restaurants[global_idx].get("visited")
                    save_data([restaurants[global_idx]])
                    st.rerun()

                # Enter Edit Mode
                if c3.button("✏️ Edit", key=f"edit_{global_idx}", use_container_width=True):
                    st.session_state[f"edit_mode_{global_idx}"] = True
                    st.rerun()

                # Delete Logic
                if f"del_confirm_{global_idx}" in st.session_state:
                    if c4.button("Confirm 🗑️", type="primary", key=f"conf_{global_idx}", use_container_width=True):
                        # Delete images
                        if r.get("images"):
                            paths = []
                            for url in r["images"]:
                                try:
                                    path = urllib.parse.urlparse(url).path
                                    prefix = f"/storage/v1/object/public/{BUCKET_NAME}/"
                                    if path.startswith(prefix):
                                        paths.append(path[len(prefix):])
                                except: pass
                            if paths: supabase.storage.from_(BUCKET_NAME).remove(paths)
                        
                        # Delete DB
                        supabase.table("restaurants").delete().eq("id", r["id"]).execute()
                        # Update Local
                        restaurants.pop(global_idx)
                        st.rerun()
                else:
                    if c4.button("Delete", key=f"del_{global_idx}", use_container_width=True):
                        st.session_state[f"del_confirm_{global_idx}"] = True
                        st.rerun()

                st.markdown("---")
                
                # Info Display
                col_info, col_notes = st.columns([1, 1])
                with col_info:
                    st.markdown(f"**📍 Address:** [{r.get('address')}]({google_maps_link(r.get('address'), r['name'])})")
                    if r.get("visited") and r.get("visited_date"):
                        st.caption(f"Visited on: {r['visited_date']}")
                    
                    if r.get("images"):
                        st.markdown("**Photos:**")
                        # Simple gallery
                        rows = len(r["images"]) // 3 + 1
                        for x in range(rows):
                            cols = st.columns(3)
                            for y in range(3):
                                img_idx = x * 3 + y
                                if img_idx < len(r["images"]):
                                    cols[y].image(r["images"][img_idx], use_column_width=True)

                with col_notes:
                    st.markdown("**📝 Notes:**")
                    if r["reviews"]:
                        for note in r["reviews"]:
                            st.info(note)
                    else:
                        st.caption("No notes yet.")

            # --- EDIT MODE ---
            else:
                st.subheader("Edit Details")
                with st.form(key=f"edit_form_{global_idx}"):
                    e_name = st.text_input("Name", r["name"])
                    c_col, p_col, l_col = st.columns(3)
                    e_cuisine = c_col.selectbox("Cuisine", CUISINES, index=CUISINES.index(r["cuisine"]) if r["cuisine"] in CUISINES else 0)
                    e_price = p_col.selectbox("Price", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
                    e_loc = l_col.selectbox("Neighborhood", NEIGHBORHOODS, index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else 0)
                    
                    e_addr = st.text_input("Address", r["address"])
                    
                    # Notes handling
                    current_notes = "\n".join(r["reviews"])
                    e_notes_block = st.text_area("Notes (one per line)", value=current_notes)
                    
                    submitted = st.form_submit_button("💾 Save Changes")
                    
                    if submitted:
                        # Geocode only if address changed
                        new_lat, new_lon = r.get("latitude"), r.get("longitude")
                        if e_addr != r["address"]:
                            new_lat, new_lon = get_lat_lon(e_addr)
                        
                        # Process notes
                        new_reviews = [n.strip() for n in e_notes_block.split('\n') if n.strip()]

                        # Update Local
                        restaurants[global_idx].update({
                            "name": e_name,
                            "cuisine": e_cuisine,
                            "price": e_price,
                            "location": e_loc,
                            "address": e_addr,
                            "reviews": new_reviews,
                            "latitude": new_lat,
                            "longitude": new_lon
                        })
                        
                        # Update DB
                        save_data([restaurants[global_idx]])
                        del st.session_state[f"edit_mode_{global_idx}"]
                        st.success("Saved!")
                        st.rerun()

                if st.button("Cancel Edit", key=f"cancel_{global_idx}"):
                    del st.session_state[f"edit_mode_{global_idx}"]
                    st.rerun()

# ────────────────────────────── Map View ──────────────────────────────
elif action == "Map View":
    st.header("Chicago Food Map 🗺️")
    
    # Folium Map Setup
    m = folium.Map(location=[41.8781, -87.6298], zoom_start=12, tiles="OpenStreetMap")
    LocateControl().add_to(m)
    marker_cluster = MarkerCluster().add_to(m)

    mapped_count = 0
    for r in restaurants:
        if r.get("latitude") and r.get("longitude"):
            mapped_count += 1
            color = "green" if r.get("visited") else "blue"
            icon_type = "glass" if r["type"] == "cocktail_bar" else "cutlery"
            
            popup_html = f"""
            <div style="width:200px">
                <b>{r['name']}</b><br>
                {r['cuisine']} • {r['price']}<br>
                <a href="{google_maps_link(r['address'])}" target="_blank">Navigate</a>
            </div>
            """
            
            folium.Marker(
                [r["latitude"], r["longitude"]],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=r["name"],
                icon=folium.Icon(color=color, icon=icon_type, prefix="glyphicon")
            ).add_to(marker_cluster)

    st_folium(m, width="100%", height=600)
    st.caption(f"Showing {mapped_count} locations.")

# ────────────────────────────── Add a Place ──────────────────────────────
elif action == "Add a Place":
    st.header("Add New Spot 📍")
    
    with st.form("add_form"):
        name = st.text_input("Name*")
        c1, c2 = st.columns(2)
        cuisine = c1.selectbox("Cuisine*", CUISINES)
        price = c2.selectbox("Price*", ["$", "$$", "$$$", "$$$$"])
        
        c3, c4 = st.columns(2)
        location = c3.selectbox("Neighborhood*", NEIGHBORHOODS)
        type_place = c4.selectbox("Type", ["restaurant", "cocktail_bar"], format_func=lambda x: "Restaurant" if x == "restaurant" else "Bar")
        
        address = st.text_input("Address*")
        
        visited = st.checkbox("Visited?")
        visited_date = st.date_input("Date") if visited else None
        
        notes = st.text_area("Initial Notes")
        images = st.file_uploader("Upload Photos", accept_multiple_files=True)
        
        submit = st.form_submit_button("Add Place", type="primary")
        
        if submit:
            if not name or not address:
                st.error("Name and Address are required.")
            else:
                with st.spinner("Geocoding & Uploading..."):
                    # 1. Geocode
                    lat, lon = get_lat_lon(address)
                    
                    # 2. Images
                    img_urls = []
                    if images:
                        img_urls = upload_images_to_supabase(images, name)
                    
                    # 3. Payload
                    new_place = {
                        "name": name,
                        "cuisine": cuisine,
                        "price": price,
                        "location": location,
                        "address": address,
                        "type": type_place,
                        "visited": visited,
                        "visited_date": visited_date.strftime("%Y-%m-%d") if visited_date and visited else None,
                        "reviews": [notes] if notes else [],
                        "images": img_urls,
                        "latitude": lat,
                        "longitude": lon
                    }
                    
                    # 4. Save
                    inserted_list = save_data([new_place], is_insert=True)
                    if inserted_list:
                        # Update session state directly
                        st.session_state.restaurants.append(inserted_list[0])
                        st.success(f"{name} added successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to save to database.")

# ────────────────────────────── Random Pick ──────────────────────────────
elif action == "Random Pick":
    st.header("Random Picker 🎲")
    
    if not restaurants:
        st.info("Add some places first!")
    else:
        with st.container(border=True):
            st.subheader("Filter Options")
            c1, c2 = st.columns(2)
            f_cuisine = c1.multiselect("Cuisine", sorted(list(set(r["cuisine"] for r in restaurants))))
            f_hood = c2.multiselect("Neighborhood", sorted(list(set(r["location"] for r in restaurants))))
            
            c3, c4 = st.columns(2)
            f_visited = c3.selectbox("Status", ["All", "Not Visited Yet", "Visited"])
            f_type = c4.selectbox("Type", ["All", "Restaurant", "Bar"])
            
            f_fav = st.checkbox("Favorites Only")
            
            if st.button("Pick Random Spot", type="primary", use_container_width=True):
                # Filter Logic
                pool = restaurants
                if f_cuisine: pool = [r for r in pool if r["cuisine"] in f_cuisine]
                if f_hood: pool = [r for r in pool if r["location"] in f_hood]
                if f_fav: pool = [r for r in pool if r.get("favorite")]
                
                if f_visited == "Not Visited Yet": pool = [r for r in pool if not r.get("visited")]
                elif f_visited == "Visited": pool = [r for r in pool if r.get("visited")]
                
                if f_type == "Restaurant": pool = [r for r in pool if r["type"] == "restaurant"]
                elif f_type == "Bar": pool = [r for r in pool if r["type"] == "cocktail_bar"]
                
                if pool:
                    choice = random.choice(pool)
                    st.session_state["last_pick"] = choice
                else:
                    st.warning("No places match those filters!")
                    if "last_pick" in st.session_state: del st.session_state["last_pick"]

        # Display Result
        if "last_pick" in st.session_state:
            r = st.session_state["last_pick"]
            st.markdown("---")
            st.success("🎉 We found a spot!")
            st.markdown(f"### {r['name']}")
            st.write(f"**{r['cuisine']}** • {r['location']}")
            st.write(f"_{r['address']}_")
            
            if r.get("images"):
                st.image(r["images"][0], caption=r["name"])
            
            st.markdown(f"[📍 Open in Maps]({google_maps_link(r['address'], r['name'])})")
