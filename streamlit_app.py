import streamlit as st
import json
import os
import random
import urllib.parse
import uuid
from datetime import datetime
import zipfile
from io import BytesIO

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
    "Chinese",
    "Italian",
    "American",
    "Mexican",
    "Japanese",
    "Indian",
    "Thai",
    "French",
    "Korean",
    "Pizza",
    "Burgers",
    "Seafood",
    "Steakhouse",
    "Bar Food",
    "Cocktails",
    "Other"
]

VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]

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
                    if "added_date" not in place:
                        place["added_date"] = datetime.now().isoformat()
                return data
        except json.JSONDecodeError:
            st.error("Data file is corrupted. Starting with empty list.")
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Load data
if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

# Page title
st.markdown("<h1 style='text-align: center;'>🍽️ Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, favorite, and randomly pick Chicago eats & drinks! 🍸</p>", unsafe_allow_html=True)

# Sidebar
st.sidebar.header("Actions")
action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Places",
     "Add a Place",
     "Random Pick (with filters)"]
)

st.sidebar.markdown("---")

with st.sidebar.expander("⚙️ Data Management"):
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
                for root, dirs, files in os.walk(IMAGES_DIR):
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

    uploaded_backup = st.file_uploader("Restore from backup (ZIP or JSON)", type=["json", "zip"], key="backup_uploader")
    if uploaded_backup and st.button("Restore Backup", type="primary"):
        try:
            if uploaded_backup.type == "application/zip" or uploaded_backup.name.endswith(".zip"):
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
                    for name in zip_file.namelist():
                        if name.startswith("images/") or name.startswith(IMAGES_DIR + "/"):
                            target_path = name if not name.startswith(IMAGES_DIR + "/") else os.path.join(os.path.dirname(IMAGES_DIR), name)
                            full_path = os.path.abspath(target_path)
                            if os.path.commonpath([full_path, os.path.abspath(IMAGES_DIR)]) == os.path.abspath(IMAGES_DIR):
                                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                                with open(full_path, "wb") as f:
                                    f.write(zip_file.read(name))
                st.success("Full backup restored successfully!")
                st.balloons()
            else:
                data = json.load(uploaded_backup)
                save_data(data)
                st.session_state.restaurants = data
                st.success("JSON backup restored")
                st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"Error restoring backup: {str(e)}")

st.sidebar.caption("Built by Alan, made for us ❤️")

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

# ========================
# View All Places
# ========================
if action == "View All Places":
    st.header("All Places")
    st.caption(f"{len(restaurants)} place(s) in your list")

    if not restaurants:
        st.info("No places added yet.")
    else:
        col_search, col_sort = st.columns([5, 3])
        with col_search:
            search_term = st.text_input(
                "🔍 Search by name, cuisine, neighborhood, or address",
                key="search_input",
                placeholder="e.g., Italian, River North"
            )
        with col_sort:
            sort_option = st.selectbox(
                "Sort by",
                options=["A-Z (Name)", "Latest Added", "Favorites First"],
                index=0,
                key="sort_select"
            )

        if search_term:
            if st.button("✖ Clear search", key="clear_search_btn"):
                st.session_state.search_input = ""
                st.rerun()

        filtered = restaurants.copy()

        if search_term:
            search_lower = search_term.lower()
            filtered = [
                r for r in filtered
                if (search_lower in r["name"].lower() or
                    search_lower in r["cuisine"].lower() or
                    search_lower in r["location"].lower() or
                    search_lower in r.get("address", "").lower())
            ]
            st.caption(f"**Found {len(filtered)} place(s)** matching '{search_term}'")

        if sort_option == "A-Z (Name)":
            sorted_places = sorted(filtered, key=lambda x: x["name"].lower())
        elif sort_option == "Latest Added":
            sorted_places = sorted(filtered, key=lambda x: x.get("added_date", ""), reverse=True)
        elif sort_option == "Favorites First":
            favorites = [r for r in filtered if r.get("favorite", False)]
            non_favorites = [r for r in filtered if not r.get("favorite", False)]
            sorted_places = sorted(favorites, key=lambda x: x["name"].lower()) + sorted(non_favorites, key=lambda x: x["name"].lower())

        st.write(f"**Showing {len(sorted_places)} place(s)**")

        for idx, r in enumerate(sorted_places):
            global_idx = restaurants.index(r)
            type_icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
            fav_icon = " ❤️" if r.get("favorite", False) else ""
            visited_icon = " ✅" if r.get("visited", False) else ""
            review_text = ""
            if r["reviews"]:
                avg = sum(rev["rating"] for rev in r["reviews"]) / len(r["reviews"])
                review_text = f" • {avg:.1f}⭐ ({len(r['reviews'])})"

            with st.expander(f"{r['name']}{type_icon}{fav_icon}{visited_icon} • {r['cuisine']} • {r['price']} • {r['location']}{review_text}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Address:** {r.get('address', 'Not provided')}")
                    maps_url = google_maps_link(r.get("address", ""), r["name"])
                    st.markdown(f"[📍 Open in Google Maps]({maps_url})")
                with col2:
                    st.button(
                        "❤️ Unfavorite" if r.get("favorite", False) else "❤️ Favorite",
                        key=f"fav_btn_{global_idx}",
                        on_click=toggle_favorite,
                        args=(global_idx,)
                    )
                    if st.button("Edit ✏️", key=f"edit_{global_idx}"):
                        st.session_state.editing_index = global_idx
                        st.rerun()
                    delete_key = f"delete_confirm_{global_idx}"
                    if delete_key in st.session_state:
                        col_del, col_cancel = st.columns(2)
                        with col_del:
                            if st.button("🗑️ Confirm Delete", key=f"confirm_{global_idx}", type="primary"):
                                delete_restaurant(global_idx)
                                del st.session_state[delete_key]
                                st.rerun()
                        with col_cancel:
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
                    for p_idx, photo_path in enumerate(r["photos"]):
                        if os.path.exists(photo_path):
                            cols[p_idx % 3].image(photo_path, use_column_width=True)

                if r["reviews"]:
                    st.write("**Reviews:**")
                    for rev in reversed(r["reviews"]):
                        st.write(f"**{'★' * rev['rating']}{'☆' * (5 - rev['rating'])}** — {rev['reviewer']} ({rev['date']})")
                        st.write(f"{rev['comment']}")
                        st.markdown("---")
                else:
                    st.write("_No reviews yet — be the first!_")

        # Edit form
        if "editing_index" in st.session_state:
            edit_idx = st.session_state.editing_index
            r = restaurants[edit_idx]
            st.markdown("---")
            st.subheader(f"Editing: {r['name']}")
            with st.form("edit_restaurant_form", clear_on_submit=False):
                new_name = st.text_input("Name*", value=r["name"])
                current_cuisine = r["cuisine"]
                cuisine_option = st.selectbox("Cuisine/Style*", options=CUISINES,
                    index=CUISINES.index(current_cuisine) if current_cuisine in CUISINES else CUISINES.index("Other"))
                new_cuisine = st.text_input("Custom cuisine*", value=current_cuisine if cuisine_option == "Other" else "") if cuisine_option == "Other" else cuisine_option
                new_price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
                current_location = r["location"]
                location_option = st.selectbox("Neighborhood*", options=NEIGHBORHOODS + ["Other"],
                    index=NEIGHBORHOODS.index(current_location) if current_location in NEIGHBORHOODS else len(NEIGHBORHOODS))
                new_location = st.text_input("Custom neighborhood*", value=current_location if location_option == "Other" else "") if location_option == "Other" else location_option
                new_address = st.text_input("Address*", value=r.get("address", ""))
                new_type = st.selectbox("Type*", options=["restaurant", "cocktail_bar"],
                    format_func=lambda x: "Restaurant 🍽️" if x == "restaurant" else "Cocktail Bar 🍸",
                    index=0 if r.get("type", "restaurant") == "restaurant" else 1)
                new_visited = st.checkbox("✅ I've already visited this place", value=r.get("visited", False))

                st.write("**Current Photos (check to delete):**")
                photos_to_delete = []
                if r.get("photos"):
                    cols = st.columns(3)
                    for p_idx, photo_path in enumerate(r["photos"]):
                        if os.path.exists(photo_path):
                            with cols[p_idx % 3]:
                                st.image(photo_path, use_column_width=True)
                                if st.checkbox("Delete this photo", key=f"del_photo_{edit_idx}_{p_idx}"):
                                    photos_to_delete.append(photo_path)

                new_photos = st.file_uploader("Add more photos (optional)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"new_photos_edit_{edit_idx}")

                col_save, col_cancel = st.columns(2)
                with col_save:
                    save_submitted = st.form_submit_button("Save Changes", type="primary")
                with col_cancel:
                    cancel = st.form_submit_button("Cancel")

                if cancel:
                    del st.session_state.editing_index
                    st.rerun()

                if save_submitted:
                    new_cuisine = new_cuisine.strip() if cuisine_option == "Other" else cuisine_option
                    new_location = new_location.strip() if location_option == "Other" else location_option
                    if not all([new_name, new_cuisine, new_location, new_address]):
                        st.error("All required fields must be filled.")
                    elif new_name.lower() != r["name"].lower() and any(existing["name"].lower() == new_name.lower() for existing in restaurants if existing != r):
                        st.warning("Another place with this name already exists!")
                    else:
                        for photo_path in photos_to_delete:
                            if os.path.exists(photo_path):
                                os.remove(photo_path)
                            if photo_path in r["photos"]:
                                r["photos"].remove(photo_path)
                        if new_photos:
                            safe_name = "".join(c for c in new_name if c.isalnum() or c in " -_").replace(" ", "_")
                            for photo in new_photos:
                                ext = photo.name.split(".")[-1].lower()
                                filename = f"{safe_name}_{uuid.uuid4().hex[:8]}.{ext}"
                                filepath = os.path.join(IMAGES_DIR, filename)
                                with open(filepath, "wb") as f:
                                    f.write(photo.getbuffer())
                                r["photos"].append(filepath)
                        r.update({
                            "name": new_name.strip(),
                            "cuisine": new_cuisine,
                            "price": new_price,
                            "location": new_location,
                            "address": new_address.strip(),
                            "type": new_type,
                            "visited": new_visited,
                        })
                        save_data(restaurants)
                        st.success(f"{new_name} updated successfully!")
                        st.balloons()
                        del st.session_state.editing_index
                        st.rerun()

# ========================
# Add a Place
# ========================
elif action == "Add a Place":
    st.header("Add a New Place")

    with st.form("add_place_form", clear_on_submit=False):
        name = st.text_input("Name*", placeholder="e.g., Lou Malnati's")
        cuisine_option = st.selectbox("Cuisine/Style*", options=CUISINES)
        cuisine = st.text_input("Custom cuisine (if 'Other')", "") if cuisine_option == "Other" else cuisine_option
        price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"])
        location_option = st.selectbox("Neighborhood*", options=NEIGHBORHOODS + ["Other"])
        location = st.text_input("Custom neighborhood (if 'Other')", "") if location_option == "Other" else location_option
        address = st.text_input("Address*", placeholder="e.g., 123 N Wacker Dr, Chicago, IL")
        place_type = st.selectbox("Type*", options=["restaurant", "cocktail_bar"],
                                  format_func=lambda x: "Restaurant 🍽️" if x == "restaurant" else "Cocktail Bar 🍸")
        visited = st.checkbox("✅ I've already visited this place")

        # Optional quick notes — right before photos
        quick_notes = st.text_area(
            "Quick notes / first impressions (optional)",
            placeholder="e.g., Amazing deep dish, must try the Malnati Chicago Classic! Great vibe.",
            height=100
        )

        uploaded_photos = st.file_uploader("Upload Photos (optional)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        submitted = st.form_submit_button("Add Place", type="primary")

        if submitted:
            final_cuisine = cuisine.strip() or cuisine_option
            final_location = location.strip() or location_option

            if not all([name.strip(), final_cuisine, final_location, address.strip()]):
                st.error("Please fill in all required fields (*)")
            elif any(r["name"].lower() == name.lower().strip() for r in restaurants):
                st.warning("This place already exists!")
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

                new_place = {
                    "name": name.strip(),
                    "cuisine": final_cuisine,
                    "price": price,
                    "location": final_location,
                    "address": address.strip(),
                    "type": place_type,
                    "favorite": False,
                    "visited": visited,
                    "photos": photo_paths,
                    "reviews": [],
                    "added_date": datetime.now().isoformat()
                }

                if quick_notes.strip():
                    review = {
                        "rating": 5,
                        "comment": quick_notes.strip(),
                        "reviewer": "You",
                        "date": datetime.now().strftime("%B %d, %Y")
                    }
                    new_place["reviews"].append(review)

                restaurants.append(new_place)
                save_data(restaurants)
                st.success(f"{name.strip()} added successfully!" + (" Notes saved!" if quick_notes.strip() else ""))
                st.balloons()
                st.rerun()

# ========================
# Random Pick
# ========================
else:  # Random Pick
    st.header("🎲 Random Place Picker")
    st.markdown("Apply filters below, then let fate decide!")

    if not restaurants:
        st.info("No places yet — add some first!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            all_cuisines = sorted({r["cuisine"] for r in restaurants})
            cuisine_filter = st.multiselect("Cuisine", options=all_cuisines, default=[])
            all_prices = sorted({r["price"] for r in restaurants}, key=lambda x: len(x))
            price_filter = st.multiselect("Price Range", options=all_prices, default=[])
            type_filter = st.selectbox("Type", options=["all", "restaurant", "cocktail_bar"],
                format_func=lambda x: {"all": "All Places", "restaurant": "Only Restaurants 🍽️", "cocktail_bar": "Only Cocktail Bars 🍸"}[x])
            only_favorites = st.checkbox("Only show favorites ❤️")
            visited_filter = st.selectbox("Visited Status", options=VISITED_OPTIONS)
        with col2:
            all_locations = sorted({r["location"] for r in restaurants})
            location_filter = st.multiselect("Neighborhood", options=all_locations, default=[])

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
            st.warning("No places match your current filters. Try broadening them!")
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
                        maps_url = google_maps_link(choice.get("address", ""), choice["name"])
                        st.markdown(f"[📍 Open in Google Maps]({maps_url})")
                        global_idx = restaurants.index(choice)
                        st.button(
                            "❤️ Remove from Favorites" if choice.get("favorite", False) else "❤️ Add to Favorites",
                            key=f"rand_fav_{global_idx}",
                            on_click=toggle_favorite,
                            args=(global_idx,)
                        )
                        if choice.get("photos"):
                            st.markdown("### Photos")
                            cols = st.columns(3)
                            for idx, photo_path in enumerate(choice["photos"]):
                                if os.path.exists(photo_path):
                                    cols[idx % 3].image(photo_path, use_column_width=True)
                        if choice["reviews"]:
                            st.markdown("### Recent Reviews")
                            for rev in choice["reviews"][-3:]:
                                st.write(f"**{'★' * rev['rating']}{'☆' * (5 - rev['rating'])}** — {rev['reviewer']} ({rev['date']})")
                                st.write(f"_{rev['comment']}_")
                        else:
                            st.info("No reviews yet — you'll be the pioneer!")
                        if st.button("🎲 Pick Again!", type="secondary", use_container_width=True):
                            choice = random.choice(filtered)
                            st.session_state.last_random_choice = choice
                            st.rerun()
                else:
                    st.info("🍽️ Your previous pick no longer matches the current filters. Hit the button for a new one!")
                    if st.button("Clear previous pick"):
                        del st.session_state.last_random_choice
                        st.rerun()
