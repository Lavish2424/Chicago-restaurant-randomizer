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
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"

# Geocoder setup - more unique and identifiable user_agent
geolocator = Nominatim(
    user_agent="AlanChicagoRestaurantBarRandomizer_v2.0",
    timeout=10
)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

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
            # Safely normalize reviews to list of non-empty strings
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
                "lat": place.get("lat"),
                "lon": place.get("lon")
            }
            if place_id:
                supabase.table("restaurants").update(update_data).eq("id", place_id).execute()
            else:
                supabase.table("restaurants").insert(update_data).execute()
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")

# Load data
if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()
restaurants = st.session_state.restaurants

st.markdown("<h1 style='text-align: center;'>🍽️🍸 Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, view, and randomly pick Chicago eats & drinks!</p>", unsafe_allow_html=True)

st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?", ["View All Places", "Add a Place", "Random Pick", "Map"])

# Clear session state on tab change
if "previous_action" not in st.session_state:
    st.session_state.previous_action = action
if st.session_state.previous_action != action:
    if "last_pick" in st.session_state:
        del st.session_state.last_pick
    keys_to_clear = [k for k in st.session_state.keys() if k.startswith("edit_mode_") or k.startswith("images_to_delete_") or k.startswith("del_confirm_") or k.startswith("edit_reviews_")]
    for k in keys_to_clear:
        del st.session_state[k]
    st.session_state.previous_action = action

st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")

NEIGHBORHOODS = ["Fulton Market", "River North", "Gold Coast", "South Loop", "Chinatown", "Pilsen", "West Town", "West Loop"]
CUISINES = ["American", "Asian", "Mexican", "Japanese", "Italian", "Indian", "Thai", "French", "Seafood", "Steakhouse", "Cocktails", "Other"]
VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]

def delete_restaurant(index):
    r = restaurants[index]
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
    del restaurants[index]
    st.session_state.restaurants = load_data()
    st.success(f"{r['name']} deleted!")
    st.rerun()

def toggle_favorite(idx):
    restaurants[idx]["favorite"] = not restaurants[idx].get("favorite", False)
    save_data(restaurants)
    st.session_state.restaurants = load_data()
    st.rerun()

def toggle_visited(idx):
    restaurants[idx]["visited"] = not restaurants[idx].get("visited", False)
    save_data(restaurants)
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
            filename = f"{sanitized_name}_{i}{file_ext}"
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

# ────────────────────────────── View All Places ──────────────────────────────
if action == "View All Places":
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
                ["A-Z (Name)", "Favorites First", "Recently Added", "Oldest First"]
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
            sorted_places = sorted(filtered, key=lambda x: x.get("id", 0), reverse=True)
        elif sort_option == "Oldest First":
            sorted_places = sorted(filtered, key=lambda x: x.get("id", 0))
        else:
            sorted_places = filtered
        for idx, r in enumerate(sorted_places):
            global_idx = restaurants.index(r)
            icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
            fav = " ❤️" if r.get("favorite") else ""
            visited = " ✅" if r.get("visited") else ""
            visited_date_str = f" (visited {r['visited_date']})" if r.get("visited") and r.get("visited_date") else ""
            img_count = f" • {len(r.get('images', []))} photo{'s' if len(r.get('images', [])) > 1 else ''}" if r.get("images") else ""
            notes_count = f" • {len(r['reviews'])} note{'s' if len(r['reviews']) != 1 else ''}" if r["reviews"] else ""
            with st.expander(f"{r['name']}{icon}{fav}{visited}{visited_date_str} • {r['cuisine']} • {r['price']} • {r['location']}{img_count}{notes_count}",
                             expanded=(f"edit_mode_{global_idx}" in st.session_state)):
                if f"edit_mode_{global_idx}" not in st.session_state:
                    # Action buttons
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
                    st.markdown("---")
                    # Address + Map link
                    col_addr, col_map = st.columns([3, 1])
                    with col_addr:
                        st.write(f"**📍 Address:** {r.get('address', 'Not provided')}")
                    with col_map:
                        st.markdown(f"[🗺️ Open in Maps]({google_maps_link(r.get('address', ''), r['name'])})", unsafe_allow_html=True)
                    # Notes - safe handling
                    if r["reviews"]:
                        st.markdown("**📝 Notes**")
                        for note in reversed(r["reviews"]):
                            if note and str(note).strip():
                                with st.container(border=True):
                                    st.write(str(note).strip())
                    else:
                        st.caption("_No notes yet — be the first to add one!_")
                    # Photos
                    if r.get("images"):
                        st.markdown("**📸 Photos**")
                        num_images = len(r["images"])
                        for i in range(0, num_images, 3):
                            cols = st.columns(3)
                            for j in range(3):
                                idx = i + j
                                if idx < num_images:
                                    with cols[j]:
                                        st.image(r["images"][idx], use_column_width=True)
                else:
                    # ==================== EDIT MODE ====================
                    st.subheader(f"Editing: {r['name']}")
                    
                    images_to_delete_key = f"images_to_delete_{global_idx}"
                    reviews_key = f"edit_reviews_{global_idx}"
                    
                    edit_name = st.text_input("Name", value=r["name"], key=f"edit_name_{global_idx}")
                    edit_cuisine = st.selectbox("Cuisine/Style", CUISINES, index=CUISINES.index(r["cuisine"]), key=f"edit_cuisine_{global_idx}")
                    edit_price = st.selectbox("Price", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]), key=f"edit_price_{global_idx}")
                    edit_location = st.selectbox("Neighborhood", NEIGHBORHOODS, index=NEIGHBORHOODS.index(r["location"]), key=f"edit_location_{global_idx}")
                    edit_address = st.text_input("Address", value=r["address"], key=f"edit_address_{global_idx}")
                    edit_type = st.selectbox("Type", ["restaurant", "cocktail_bar"],
                                             index=0 if r["type"] == "restaurant" else 1,
                                             format_func=lambda x: "Restaurant 🍽️" if x=="restaurant" else "Cocktail Bar 🍸",
                                             key=f"edit_type_{global_idx}")
                    edit_visited = st.checkbox("✅ I've already visited this place", value=r.get("visited", False), key=f"edit_visited_{global_idx}")
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
                    new_images = st.file_uploader("Upload additional photos", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True, key=f"edit_images_{global_idx}")
                    
                    if r.get("images"):
                        st.markdown("### Current photos")
                        if images_to_delete_key not in st.session_state:
                            st.session_state[images_to_delete_key] = set()
                        cols = st.columns(3)
                        for i, img_url in enumerate(r["images"]):
                            with cols[i % 3]:
                                st.image(img_url, use_column_width=True)
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
                            st.write("")
                            st.write("")
                            if st.button("🗑️", key=f"del_rev_{global_idx}_{rev_idx}"):
                                st.session_state[reviews_key].pop(rev_idx)
                                st.rerun()
                        if new_note != note:
                            st.session_state[reviews_key][rev_idx] = new_note
                    
                    st.markdown("**Add a new note**")
                    new_note_text = st.text_area("New note (optional)", height=100, key=f"new_note_{global_idx}")
                    if new_note_text.strip():
                        if st.button("➕ Add Note", key=f"add_note_btn_{global_idx}"):
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
                                for url in st.session_state[images_to_delete_key]:
                                    if url in remaining_images:
                                        remaining_images.remove(url)
                                    try:
                                        parsed = urllib.parse.urlparse(url)
                                        path = parsed.path
                                        prefix = f"/storage/v1/object/public/{BUCKET_NAME}/"
                                        if path.startswith(prefix):
                                            file_path = path[len(prefix):]
                                            supabase.storage.from_(BUCKET_NAME).remove([file_path])
                                    except:
                                        pass
                            if edit_address.strip() != r["address"]:
                                full_address = f"{edit_address.strip()}, Chicago, IL"
                                with st.spinner("Finding location on map..."):
                                    try:
                                        location_geo = geocode(full_address)
                                        if location_geo:
                                            new_lat = location_geo.latitude
                                            new_lon = location_geo.longitude
                                        else:
                                            st.warning("Could not find coordinates for this address. It will not appear on the map. Try a more specific address.")
                                            new_lat = new_lon = None
                                    except Exception as e:
                                        st.error(f"Geocoding error: {str(e)}")
                                        new_lat = new_lon = None
                            else:
                                new_lat = r.get("lat")
                                new_lon = r.get("lon")
                            updated_date_str = visited_date_edit.strftime("%B %d, %Y") if visited_date_edit else None
                            cleaned_reviews = [n.strip() for n in st.session_state.get(reviews_key, r["reviews"]) if n and n.strip()]
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
                                "lat": new_lat,
                                "lon": new_lon,
                                "reviews": cleaned_reviews
                            })
                            save_data(restaurants)
                            st.session_state.restaurants = load_data()
                            del st.session_state[f"edit_mode_{global_idx}"]
                            if images_to_delete_key in st.session_state:
                                del st.session_state[images_to_delete_key]
                            if reviews_key in st.session_state:
                                del st.session_state[reviews_key]
                            st.success("Changes saved!")
                            st.rerun()
                    with col_cancel:
                        if st.button("❌ Cancel", use_container_width=True, key=f"cancel_{global_idx}"):
                            del st.session_state[f"edit_mode_{global_idx}"]
                            if images_to_delete_key in st.session_state:
                                del st.session_state[images_to_delete_key]
                            if reviews_key in st.session_state:
                                del st.session_state[reviews_key]
                            st.rerun()

# ────────────────────────────── Add a Place ──────────────────────────────
elif action == "Add a Place":
    st.header("Add a New Place 📍")
    name = st.text_input("Name*")
    cuisine = st.selectbox("Cuisine/Style*", CUISINES)
    price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"])
    location = st.selectbox("Neighborhood*", NEIGHBORHOODS)
    address = st.text_input("Address*")
    place_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"],
                              format_func=lambda x: "Restaurant 🍽️" if x=="restaurant" else "Cocktail Bar 🍸")
  
    visited = st.checkbox("✅ I've already visited this place")
  
    default_date = date.today() if visited else None
  
    visited_date_input = st.date_input(
        "Date Visited (optional)",
        value=default_date,
        key="visited_date_key"
    )
  
    visited_date = visited_date_input if visited_date_input is not None else None
  
    uploaded_images = st.file_uploader("Upload photos", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
    quick_notes = st.text_area("Quick notes (optional)", height=100)
  
    if st.button("Add Place", type="primary"):
        if not all([name.strip(), address.strip()]):
            st.error("Name and address required")
        elif any(r["name"].lower() == name.lower().strip() for r in restaurants):
            st.warning("Already exists!")
        else:
            image_urls = []
            if uploaded_images:
                with st.spinner("Uploading images..."):
                    image_urls = upload_images_to_supabase(uploaded_images, name)
          
            visited_date_str = visited_date.strftime("%B %d, %Y") if visited_date else None
            full_address = f"{address.strip()}, Chicago, IL"
            lat = lon = None
            with st.spinner("Finding location for map..."):
                try:
                    geo_location = geocode(full_address)
                    if geo_location:
                        lat = geo_location.latitude
                        lon = geo_location.longitude
                    else:
                        st.warning("Could not find coordinates for this address — it won't appear on the map. Check spelling or add more details (e.g., '123 N Michigan Ave').")
                except Exception as e:
                    st.error(f"Geocoding error: {str(e)}")
          
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
                "lat": lat,
                "lon": lon
            }
          
            try:
                supabase.table("restaurants").insert(new).execute()
                st.session_state.restaurants = load_data()
                st.success(f"{name} added! {'Pinned on map 🗺️' if lat and lon else 'Address not mapped yet'}")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add place: {str(e)}")

# ────────────────────────────── Map ──────────────────────────────
elif action == "Map":
    st.header("Interactive Map 🗺️")
 
    places_with_coords = [r for r in restaurants if r.get("lat") and r.get("lon")]
 
    if not places_with_coords:
        st.info("No places with coordinates yet. Add places with valid Chicago addresses to see them on the map!")
        st.stop()
 
    m = folium.Map(location=[41.8781, -87.6298], zoom_start=12, tiles="OpenStreetMap")
 
    for place in places_with_coords:
        icon_color = "red" if place.get("visited") else "blue"
        icon_symbol = "cutlery" if place["type"] == "restaurant" else "glass-martini"
     
        popup_html = f"""
        <b>{place['name']}</b><br>
        {place['cuisine']} • {place['price']} • {place['location']}<br>
        {place['address']}<br>
        {"Visited: " + place.get('visited_date', '') if place.get('visited') else "Not visited yet"}
        """
        popup = folium.Popup(popup_html, max_width=300)
     
        folium.Marker(
            [place['lat'], place['lon']],
            popup=popup,
            tooltip=place['name'],
            icon=folium.Icon(color=icon_color, icon=icon_symbol, prefix='fa')
        ).add_to(m)
 
    legend_html = '''
    <div style="
        position: fixed;
        bottom: 10px; left: 10px; width: 150px; height: 130px;
        background-color: white; border:2px solid grey; border-radius:6px;
        z-index:9999; font-size:14px; padding: 10px;
        ">
      <b>Legend</b><br>
      &nbsp;<i class="fa fa-map-marker fa-2x" style="color:blue"></i>&nbsp; Not visited yet<br>
      &nbsp;<i class="fa fa-map-marker fa-2x" style="color:red"></i>&nbsp; Already visited<br><br>
      &nbsp;<i class="fa fa-cutlery fa-2x" style="color:gray"></i>&nbsp; Restaurant 🍽️<br>
      &nbsp;<i class="fa fa-glass-martini fa-2x" style="color:gray"></i>&nbsp; Cocktail Bar 🍸
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
 
    st_folium(m, width=700, height=500, key="map")

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
                                         format_func=lambda x: {"all":"All", "restaurant":"Restaurants 🍽️", "cocktail_bar":"Bars 🍸"}[x])
            with c5:
                visited_filter = st.selectbox("Visited Status", VISITED_OPTIONS)
            with c6:
                st.write("")
                st.write("")
                only_fav = st.checkbox("❤️ Favorites only")
        filtered = [r for r in restaurants
                    if (not only_fav or r.get("favorite"))
                    and (type_filter == "all" or r.get("type") == type_filter)
                    and (not cuisine_filter or r["cuisine"] in cuisine_filter)
                    and (not price_filter or r["price"] in price_filter)
                    and (not location_filter or r["location"] in location_filter)
                    and (visited_filter == "All" or
                         (visited_filter == "Visited Only" and r.get("visited")) or
                         (visited_filter == "Not Visited Yet" and not r.get("visited")))]
        st.caption(f"**{len(filtered)} places** match your filters")
        if not filtered:
            st.warning("No matches – try broader filters!")
        else:
            if st.button("🎲 Pick Random Place!", type="primary", use_container_width=True):
                picked = random.choice(filtered)
                st.session_state.last_pick = picked
                st.rerun()
            if "last_pick" in st.session_state:
                c = st.session_state.last_pick
                if c in filtered:
                    st.markdown("---")
                    with st.container(border=True):
                        tag = " 🍸 Cocktail Bar" if c.get("type")=="cocktail_bar" else " 🍽️ Restaurant"
                        fav = " ❤️" if c.get("favorite") else ""
                        vis = " ✅ Visited" if c.get("visited") else ""
                        vis_date = f" ({c.get('visited_date')})" if c.get("visited_date") else ""
                        st.markdown(f"# {c['name']}{tag}{fav}{vis}{vis_date}")
                        st.markdown(f"**{c['cuisine']} • {c['price']} • {c['location']}**")
                        idx = restaurants.index(c)
                        col_fav, col_vis = st.columns(2)
                        with col_fav:
                            if st.button("❤️ Unfavorite" if c.get("favorite") else "❤️ Favorite", key=f"rand_fav_{idx}", use_container_width=True):
                                toggle_favorite(idx)
                        with col_vis:
                            if st.button("✅ Mark as Unvisited" if c.get("visited") else "✅ Mark as Visited", key=f"rand_vis_{idx}", type="secondary", use_container_width=True):
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
                                    st.image(img_url, use_column_width=True)
                        st.markdown("---")
                        if st.button("🎲 Pick Again (from same filters)", type="secondary", use_container_width=True):
                            picked = random.choice(filtered)
                            st.session_state.last_pick = picked
                            st.rerun()
                else:
                    st.info("Previous pick no longer matches current filters — pick again!")
