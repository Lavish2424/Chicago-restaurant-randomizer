import streamlit as st
import json
import os
import random
import urllib.parse
import uuid
from datetime import datetime
import zipfile
from io import BytesIO
import pandas as pd
import pydeck as pdk
import requests
import time

DATA_FILE = "restaurants.json"
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

NEIGHBORHOODS = [
    "Fulton Market",
    "River North",
    "Gold Coast",
    "South Loop",
    "Chinatown",
    "Pilsen",
    "West Town"
]

CUISINES = [
    "Chinese", "Italian", "American", "Mexican", "Japanese", "Indian",
    "Thai", "French", "Korean", "Pizza", "Burgers", "Seafood",
    "Steakhouse", "Bar Food", "Cocktails", "Other"
]

VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]

# Simple Nominatim geocoding (free, no API key, respectful rate limit)
@st.cache_data(ttl=86400)  # Cache for 24 hours
def geocode_address(address: str):
    try:
        time.sleep(1)  # Respect Nominatim usage policy
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address + ", Chicago, IL",
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": "ChicagoRestaurantApp/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None, None

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for place in data:
                    if "favorite" not in place:
                        place["favorite"] = False
                    if "visited" not in place:
                        place["visited"] = False
                    if "photos" not in place:
                        place["photos"] = []
                    if "reviews" not in place:
                        place["reviews"] = []
                    if "lat" not in place:
                        place["lat"] = None
                    if "lng" not in place:
                        place["lng"] = None
                return data
        except json.JSONDecodeError:
            st.error("Data file is corrupted. Starting with empty list.")
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Load data into session state
if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

# Page title
st.markdown("<h1 style='text-align: center;'>🍽️ Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, edit, delete, review, favorite, randomly pick, and view on map! 🗺️</p>", unsafe_allow_html=True)

# Sidebar
st.sidebar.header("Actions")
action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Places",
     "Favorites ❤️",
     "Add a Place",
     "Add a Review",
     "Random Pick (with filters)",
     "Map View 🗺️"]
)

st.sidebar.markdown("---")
with st.sidebar.expander("⚙️ Data Management"):
    # DOWNLOAD BACKUP
    if st.button("Download backup (JSON + Images)"):
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            if os.path.exists(DATA_FILE):
                zip_file.write(DATA_FILE, os.path.basename(DATA_FILE))
            else:
                empty_data = []
                json_bytes = json.dumps(empty_data, indent=4).encode('utf-8')
                zip_file.writestr(os.path.basename(DATA_FILE), json_bytes)
            if os.path.exists(IMAGES_DIR):
                for root, _, files in os.walk(IMAGES_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=os.path.dirname(IMAGES_DIR))
                        zip_file.write(file_path, arcname)
        zip_buffer.seek(0)
        st.download_button(
            label="📥 Download full backup (ZIP)",
            data=zip_buffer.getvalue(),
            file_name=f"chicago_restaurants_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip"
        )

    # RESTORE FROM BACKUP
    uploaded_backup = st.file_uploader("Restore from backup (ZIP or JSON)", type=["json", "zip"], key="backup_uploader")
    if uploaded_backup and st.button("Restore Backup", type="primary"):
        try:
            if uploaded_backup.name.endswith(".zip"):
                with zipfile.ZipFile(uploaded_backup, "r") as zip_file:
                    json_found = False
                    for name in zip_file.namelist():
                        if os.path.basename(name) == os.path.basename(DATA_FILE):
                            data_bytes = zip_file.read(name)
                            data = json.loads(data_bytes)
                            save_data(data)
                            st.session_state.restaurants = data
                            json_found = True
                            break
                    if not json_found:
                        st.error("ZIP file does not contain restaurants.json")
                        st.stop()
                    # Extract images
                    for name in zip_file.namelist():
                        if name.startswith("images/") or name.startswith(IMAGES_DIR + "/"):
                            target_path = name if name.startswith("images/") else os.path.join(os.path.dirname(IMAGES_DIR), name)
                            full_path = os.path.abspath(target_path)
                            if os.path.commonpath([full_path, os.path.abspath(IMAGES_DIR)]) == os.path.abspath(IMAGES_DIR):
                                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                                with open(full_path, "wb") as f:
                                    f.write(zip_file.read(name))
                st.success("Full backup restored!")
                st.balloons()
            else:
                data = json.load(uploaded_backup)
                save_data(data)
                st.session_state.restaurants = data
                st.success("JSON backup restored (images not included)")
                st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"Error restoring backup: {str(e)}")

st.sidebar.caption("Built by Alan, made for us ❤️ • Now with map view!")

# ====================== MAP VIEW TAB ======================
if action == "Map View 🗺️":
    st.header("🗺️ All Places on Map")

    if not restaurants:
        st.info("No places added yet. Add some to see them on the map!")
    else:
        map_data = []
        missing_coords = 0

        for r in restaurants:
            lat = r.get("lat")
            lng = r.get("lng")

            # Auto-geocode if missing
            if (lat is None or lng is None) and r.get("address"):
                lat, lng = geocode_address(r["address"])
                if lat and lng:
                    r["lat"] = lat
                    r["lng"] = lng
                    save_data(restaurants)

            if lat is not None and lng is not None:
                type_icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
                fav = " ❤️" if r.get("favorite", False) else ""
                visited = " ✅" if r.get("visited", False) else ""
                tooltip = f"""
                <b>{r['name']}</b>{type_icon}{fav}{visited}<br>
                {r['cuisine']} • {r['price']}<br>
                {r['location']}<br>
                <i>{r.get('address', '')}</i>
                """
                map_data.append({
                    "name": r["name"],
                    "lat": float(lat),
                    "lon": float(lng),
                    "tooltip": tooltip,
                    "color": [255, 80, 80] if r.get("favorite", False) else [80, 140, 255]
                })
            else:
                missing_coords += 1

        if missing_coords > 0:
            st.warning(f"{missing_coords} place(s) could not be geocoded (check address).")

        if map_data:
            df = pd.DataFrame(map_data)

            view_state = pdk.ViewState(
                latitude=41.8781,
                longitude=-87.6298,
                zoom=11,
                pitch=0
            )

            layer = pdk.Layer(
                "ScatterplotLayer",
                data=df,
                get_position="[lon, lat]",
                get_color="color",
                get_radius=45,
                pickable=True,
                auto_highlight=True,
            )

            tooltip = {
                "html": "{tooltip}",
                "style": {"backgroundColor": "white", "color": "black", "fontFamily": "Helvetica, Arial", "padding": "10px"}
            }

            deck = pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip=tooltip
            )

            st.pydeck_chart(deck, use_container_width=True)
            st.caption("❤️ Red pins = Favorites • Blue pins = Others • Hover/click for details")
        else:
            st.info("No places with valid coordinates yet.")

# ====================== OTHER ACTIONS ======================
else:
    def delete_restaurant(index):
        r = restaurants[index]
        if r.get("photos"):
            for photo_path in r["photos"]:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
        del restaurants[index]
        save_data(restaurants)
        st.success(f"{r['name']} deleted successfully.")
        st.balloons()

    def toggle_favorite(idx):
        restaurants[idx]["favorite"] = not restaurants[idx].get("favorite", False)
        save_data(restaurants)

    def google_maps_link(address, name=""):
        query = f"{name}, {address}" if name else address
        encoded = urllib.parse.quote(query)
        return f"https://www.google.com/maps/search/?api=1&query={encoded}"

    # Header
    if action == "View All Places":
        st.header("All Places")
        st.caption(f"{len(restaurants)} place(s) in your list")
    elif action == "Favorites ❤️":
        st.header("❤️ Your Favorite Places")
    elif action == "Add a Place":
        st.header("Add New Place")
    elif action == "Add a Review":
        st.header("Leave a Review")
    elif action == "Random Pick (with filters)":
        st.header("🎲 Random Place Picker")
        st.markdown("Apply filters below, then let fate decide!")

    # View All / Favorites
    if action in ["View All Places", "Favorites ❤️"]:
        display_places = [r for r in restaurants if r.get("favorite", False)] if action == "Favorites ❤️" else restaurants
        if not display_places:
            st.info("No favorites yet!" if action == "Favorites ❤️" else "No places added yet.")
        else:
            col_search, col_clear = st.columns([6, 1])
            with col_search:
                search_term = st.text_input("🔍 Search by name, cuisine, neighborhood, or address", key="search_input")
            with col_clear:
                if search_term and st.button("✖", key="clear_search"):
                    st.session_state.search_input = ""
                    st.rerun()

            filtered = display_places
            if search_term:
                search_lower = search_term.lower()
                filtered = [r for r in filtered if search_lower in r["name"].lower() or
                            search_lower in r["cuisine"].lower() or
                            search_lower in r["location"].lower() or
                            search_lower in r.get("address", "").lower()]
                st.write(f"**Found {len(filtered)} place(s)**")

            for idx, r in enumerate(sorted(filtered, key=lambda x: x["name"].lower())):
                global_idx = restaurants.index(r)
                type_icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
                fav_icon = " ❤️" if r.get("favorite", False) else ""
                visited_icon = " ✅" if r.get("visited", False) else ""
                review_text = f" • {sum(rev['rating'] for rev in r['reviews'])/len(r['reviews']):.1f}⭐ ({len(r['reviews'])})" if r["reviews"] else ""
                with st.expander(f"{r['name']}{type_icon}{fav_icon}{visited_icon} • {r['cuisine']} • {r['price']} • {r['location']}{review_text}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Address:** {r.get('address', 'Not provided')}")
                        st.markdown(f"[📍 Open in Google Maps]({google_maps_link(r.get('address', ''), r['name'])})")
                    with col2:
                        st.button("❤️ Unfavorite" if r.get("favorite", False) else "❤️ Favorite",
                                  key=f"fav_{global_idx}", on_click=toggle_favorite, args=(global_idx,))
                        if st.button("Edit ✏️", key=f"edit_{global_idx}"):
                            st.session_state.editing_index = global_idx
                            st.rerun()
                        delete_key = f"del_confirm_{global_idx}"
                        if delete_key in st.session_state:
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("🗑️ Confirm Delete", key=f"confirm_{global_idx}", type="primary"):
                                    delete_restaurant(global_idx)
                                    del st.session_state[delete_key]
                                    st.rerun()
                            with c2:
                                if st.button("Cancel", key=f"cancel_{global_idx}"):
                                    del st.session_state[delete_key]
                                    st.rerun()
                        else:
                            if st.button("Delete 🗑️", key=f"delete_{global_idx}", type="secondary"):
                                st.session_state[delete_key] = True
                                st.rerun()

                    if r.get("photos"):
                        st.write("**Photos:**")
                        cols = st.columns(3)
                        for i, photo_path in enumerate(r["photos"]):
                            if os.path.exists(photo_path):
                                cols[i % 3].image(photo_path, use_column_width=True)

                    if r["reviews"]:
                        st.write("**Reviews:**")
                        for rev in reversed(r["reviews"]):
                            st.write(f"**{'★'*rev['rating']}{'☆'*(5-rev['rating'])}** — {rev['reviewer']} ({rev['date']})")
                            st.write(rev['comment'])
                            st.markdown("---")
                    else:
                        st.write("_No reviews yet — be the first!_")

            # Edit form
            if "editing_index" in st.session_state:
                edit_idx = st.session_state.editing_index
                r = restaurants[edit_idx]
                st.markdown("---")
                st.subheader(f"Editing: {r['name']}")
                with st.form("edit_form"):
                    new_name = st.text_input("Name*", value=r["name"])
                    cuisine_option = st.selectbox("Cuisine*", options=CUISINES, index=CUISINES.index(r["cuisine"]) if r["cuisine"] in CUISINES else CUISINES.index("Other"))
                    new_cuisine = st.text_input("Custom cuisine*", value=r["cuisine"]) if cuisine_option == "Other" else cuisine_option
                    new_price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
                    location_option = st.selectbox("Neighborhood*", options=NEIGHBORHOODS + ["Other"], index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else len(NEIGHBORHOODS))
                    new_location = st.text_input("Custom neighborhood*", value=r["location"]) if location_option == "Other" else location_option
                    new_address = st.text_input("Address*", value=r.get("address", ""))
                    new_type = st.selectbox("Type*", options=["restaurant", "cocktail_bar"], format_func=lambda x: "Restaurant 🍽️" if x == "restaurant" else "Cocktail Bar 🍸",
                                            index=0 if r.get("type", "restaurant") == "restaurant" else 1)
                    new_visited = st.checkbox("✅ Visited", value=r.get("visited", False))

                    col_lat, col_lng = st.columns(2)
                    with col_lat:
                        manual_lat = st.text_input("Latitude (optional)", value=r.get("lat", "") or "")
                    with col_lng:
                        manual_lng = st.text_input("Longitude (optional)", value=r.get("lng", "") or "")

                    # Photos handling (delete + add)
                    photos_to_delete = []
                    if r.get("photos"):
                        st.write("**Current Photos (check to delete):**")
                        cols = st.columns(3)
                        for i, photo_path in enumerate(r["photos"]):
                            if os.path.exists(photo_path):
                                with cols[i % 3]:
                                    st.image(photo_path, use_column_width=True)
                                    if st.checkbox("Delete", key=f"del_p_{edit_idx}_{i}"):
                                        photos_to_delete.append(photo_path)
                    new_photos = st.file_uploader("Add more photos", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"new_ph_{edit_idx}")

                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        save = st.form_submit_button("Save Changes", type="primary")
                    with col_cancel:
                        cancel = st.form_submit_button("Cancel")

                    if cancel:
                        del st.session_state.editing_index
                        st.rerun()
                    if save:
                        new_cuisine = new_cuisine.strip() if cuisine_option == "Other" else cuisine_option
                        new_location = new_location.strip() if location_option == "Other" else location_option
                        lat = float(manual_lat) if manual_lat.strip() else None
                        lng = float(manual_lng) if manual_lng.strip() else None

                        if not all([new_name, new_cuisine, new_location, new_address]):
                            st.error("Required fields missing.")
                        else:
                            # Delete photos
                            for p in photos_to_delete:
                                if os.path.exists(p):
                                    os.remove(p)
                                if p in r["photos"]:
                                    r["photos"].remove(p)
                            # Add new photos
                            if new_photos:
                                safe_name = "".join(c for c in new_name if c.isalnum() or c in " -_").replace(" ", "_")
                                for photo in new_photos:
                                    ext = photo.name.split(".")[-1].lower()
                                    filename = f"{safe_name}_{uuid.uuid4().hex[:8]}.{ext}"
                                    filepath = os.path.join(IMAGES_DIR, filename)
                                    with open(filepath, "wb") as f:
                                        f.write(photo.getbuffer())
                                    r["photos"].append(filepath)
                            # Update
                            r.update({
                                "name": new_name.strip(),
                                "cuisine": new_cuisine,
                                "price": new_price,
                                "location": new_location,
                                "address": new_address.strip(),
                                "type": new_type,
                                "visited": new_visited,
                                "lat": lat,
                                "lng": lng
                            })
                            save_data(restaurants)
                            st.success("Updated!")
                            st.balloons()
                            del st.session_state.editing_index
                            st.rerun()

    # Add a Place
    elif action == "Add a Place":
        with st.form("add_place_form"):
            name = st.text_input("Name*", placeholder="e.g., Lou Malnati's")
            cuisine_option = st.selectbox("Cuisine/Style*", options=CUISINES)
            cuisine = st.text_input("Custom cuisine*", placeholder="e.g., Vietnamese") if cuisine_option == "Other" else cuisine_option
            price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"])
            location_option = st.selectbox("Neighborhood*", options=NEIGHBORHOODS + ["Other"])
            location = st.text_input("Custom neighborhood*", placeholder="e.g., Logan Square") if location_option == "Other" else location_option
            address = st.text_input("Address*", placeholder="e.g., 123 N Wacker Dr, Chicago, IL")
            place_type = st.selectbox("Type*", options=["restaurant", "cocktail_bar"],
                                      format_func=lambda x: "Restaurant 🍽️" if x == "restaurant" else "Cocktail Bar 🍸")
            visited = st.checkbox("✅ I've already visited this place")

            col_lat, col_lng = st.columns(2)
            with col_lat:
                manual_lat = st.text_input("Latitude (optional)", placeholder="e.g., 41.8781")
            with col_lng:
                manual_lng = st.text_input("Longitude (optional)", placeholder="e.g., -87.6298")

            uploaded_photos = st.file_uploader("Upload Photos (optional)", type=["jpg","jpeg","png"], accept_multiple_files=True)

            submitted = st.form_submit_button("Add Place", type="primary")
            if submitted:
                cuisine = cuisine.strip() if cuisine_option == "Other" else cuisine_option
                location = location.strip() if location_option == "Other" else location_option
                lat = float(manual_lat) if manual_lat.strip() else None
                lng = float(manual_lng) if manual_lng.strip() else None

                if not all([name, cuisine, location, address]):
                    st.error("Please fill all required fields.")
                elif any(r["name"].lower() == name.lower() for r in restaurants):
                    st.warning("Place already exists!")
                else:
                    photo_paths = []
                    if uploaded_photos:
                        safe_name = "".join(c for c in name if c.isalnum() or c in " -_").replace(" ", "_")
                        for photo in uploaded_photos:
                            ext = photo.name.split(".")[-1].lower()
                            filename = f"{safe_name}_{uuid.uuid4().hex[:8]}.{ext}"
                            filepath = os.path.join(IMAGES_DIR, filename)
                            with open(filepath, "wb") as f:
                                f.write(photo.getbuffer())
                            photo_paths.append(filepath)

                    restaurants.append({
                        "name": name.strip(),
                        "cuisine": cuisine,
                        "price": price,
                        "location": location,
                        "address": address.strip(),
                        "type": place_type,
                        "favorite": False,
                        "visited": visited,
                        "photos": photo_paths,
                        "reviews": [],
                        "lat": lat,
                        "lng": lng
                    })
                    save_data(restaurants)
                    st.success(f"{name} added!")
                    st.balloons()
                    st.rerun()

    # Add a Review
    elif action == "Add a Review":
        if not restaurants:
            st.info("No places yet — add one first!")
        else:
            names = [r["name"] for r in restaurants]
            selected = st.selectbox("Choose place to review", names)
            with st.form("review_form", clear_on_submit=True):
                rating = st.radio("Rating", options=[1,2,3,4,5], format_func=lambda x: "★"*x + "☆"*(5-x), horizontal=True)
                comment = st.text_area("Your thoughts*", placeholder="What did you like?")
                reviewer = st.text_input("Your name (optional)")
                submitted = st.form_submit_button("Submit Review", type="primary")
                if submitted:
                    if not comment.strip():
                        st.error("Write a comment!")
                    else:
                        review = {
                            "rating": rating,
                            "comment": comment.strip(),
                            "reviewer": reviewer.strip() or "Anonymous",
                            "date": datetime.now().strftime("%B %d, %Y")
                        }
                        for r in restaurants:
                            if r["name"] == selected:
                                r["reviews"].append(review)
                                break
                        save_data(restaurants)
                        st.success("Review added!")
                        st.balloons()
                        st.rerun()

    # Random Pick
    elif action == "Random Pick (with filters)":
        if not restaurants:
            st.info("No places yet — add some first!")
        else:
            col1, col2 = st.columns(2)
            with col1:
                all_cuisines = sorted({r["cuisine"] for r in restaurants})
                cuisine_filter = st.multiselect("Cuisine", options=all_cuisines)
                all_prices = sorted({r["price"] for r in restaurants}, key=lambda x: len(x))
                price_filter = st.multiselect("Price Range", options=all_prices)
                type_filter = st.selectbox("Type", options=["all", "restaurant", "cocktail_bar"],
                                           format_func=lambda x: {"all":"All", "restaurant":"Restaurants 🍽️", "cocktail_bar":"Cocktail Bars 🍸"}[x])
                only_favorites = st.checkbox("Only favorites ❤️")
                visited_filter = st.selectbox("Visited Status", options=VISITED_OPTIONS)
            with col2:
                all_locations = sorted({r["location"] for r in restaurants})
                location_filter = st.multiselect("Neighborhood", options=all_locations)

            filtered = restaurants.copy()
            if only_favorites:
                filtered = [r for r in filtered if r.get("favorite", False)]
            if type_filter != "all":
                filtered = [r for r in filtered if r.get("type", "restaurant") == type_filter]
            if cuisine_filter:
                filtered = [r for r in filtered if r["cuisine"] in cuisine_filter]
            if price_filter:
                filtered = [r for r in filtered if r["price"] in price_filter]
            if location_filter:
                filtered = [r for r in filtered if r["location"] in location_filter]
            if visited_filter == "Visited Only":
                filtered = [r for r in filtered if r.get("visited", False)]
            elif visited_filter == "Not Visited Yet":
                filtered = [r for r in filtered if not r.get("visited", False)]

            st.write(f"**{len(filtered)} place(s)** match your filters.")
            if len(filtered) == 0:
                st.warning("No matches — broaden filters!")
            else:
                if st.button("🎲 Pick Random Place!", type="primary", use_container_width=True):
                    choice = random.choice(filtered)
                    st.session_state.last_random_choice = choice
                    st.balloons()
                    st.rerun()

                if "last_random_choice" in st.session_state:
                    choice = st.session_state.last_random_choice
                    if choice in filtered:
                        st.markdown("### 🎉 **Your Random Pick Is...**")
                        with st.container(border=True):
                            type_tag = " 🍸 Cocktail Bar" if choice.get("type") == "cocktail_bar" else " 🍽️ Restaurant"
                            fav_tag = " ❤️" if choice.get("favorite", False) else ""
                            visited_tag = " ✅ Visited" if choice.get("visited", False) else ""
                            st.markdown(f"# {choice['name']}{type_tag}{fav_tag}{visited_tag}")
                            st.write(f"**Cuisine:** {choice['cuisine']} • **Price:** {choice['price']} • **Location:** {choice['location']}")
                            st.write(f"**Address:** {choice.get('address', 'Not provided')}")
                            st.markdown(f"[📍 Open in Google Maps]({google_maps_link(choice.get('address', ''), choice['name'])})")
                            idx = restaurants.index(choice)
                            st.button("❤️ Remove Favorite" if choice.get("favorite", False) else "❤️ Add to Favorites",
                                      key=f"rand_fav_{idx}", on_click=toggle_favorite, args=(idx,))

                            if choice.get("photos"):
                                st.markdown("### Photos")
                                cols = st.columns(3)
                                for i, p in enumerate(choice["photos"]):
                                    if os.path.exists(p):
                                        cols[i % 3].image(p, use_column_width=True)

                            if choice["reviews"]:
                                st.markdown("### Recent Reviews")
                                for rev in choice["reviews"][-3:]:
                                    st.write(f"**{'★'*rev['rating']}{'☆'*(5-rev['rating'])}** — {rev['reviewer']} ({rev['date']})")
                                    st.write(f"_{rev['comment']}_")
                            else:
                                st.info("No reviews yet!")

                            if st.button("🎲 Pick Again!", type="secondary", use_container_width=True):
                                choice = random.choice(filtered)
                                st.session_state.last_random_choice = choice
                                st.rerun()
                    else:
                        st.info("Previous pick no longer matches filters. Pick again!")
                        if st.button("Clear previous"):
                            del st.session_state.last_random_choice
                            st.rerun()
