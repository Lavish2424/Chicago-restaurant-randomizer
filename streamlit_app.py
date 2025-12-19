import streamlit as st
import json
import os
import random
import urllib.parse
import uuid
from datetime import datetime
import zipfile
from io import BytesIO
import requests
import pandas as pd

DATA_FILE = "restaurants.json"
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

NEIGHBORHOODS = [
    "Fulton Market", "River North", "Gold Coast", "South Loop",
    "Chinatown", "Pilsen", "West Town"
]

CUISINES = [
    "Chinese", "Italian", "American", "Mexican", "Japanese", "Indian",
    "Thai", "French", "Korean", "Pizza", "Burgers", "Seafood",
    "Steakhouse", "Bar Food", "Cocktails", "Other"
]

VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]
SORT_OPTIONS = [
    "Name (A-Z)", "Recently Added", "Highest Rating", "Last Visited (Newest)", "Random"
]

HISTORY_FILE = "pick_history.json"
MAX_HISTORY = 15

def geocode_address(address, name):
    """Simple geocoding using Nominatim (OpenStreetMap) – no API key needed"""
    query = f"{name}, {address}, Chicago, IL"
    encoded = urllib.parse.quote(query)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1"
    headers = {"User-Agent": "ChicagoRestaurantApp/1.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        pass
    return None, None

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for place in data:
                    if "favorite" not in place: place["favorite"] = False
                    if "visited" not in place: place["visited"] = False
                    if "visited_date" not in place: place["visited_date"] = None
                    if "photos" not in place: place["photos"] = []
                    if "reviews" not in place: place["reviews"] = []
                    if "notes" not in place: place["notes"] = ""
                    if "lat" not in place: place["lat"] = None
                    if "lng" not in place: place["lng"] = None
                return data
        except json.JSONDecodeError:
            st.error("Data file corrupted. Starting fresh.")
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[-MAX_HISTORY:], f, indent=4)

if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants
pick_history = load_history()

# Counts for sidebar badges
total_places = len(restaurants)
favorites_count = sum(1 for r in restaurants if r.get("favorite", False))
not_visited_count = sum(1 for r in restaurants if not r.get("visited", False))

st.markdown("<h1 style='text-align: center;'>🍽️ Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, explore, review, and discover Chicago's best spots!</p>", unsafe_allow_html=True)

# Sidebar
st.sidebar.header("Actions")
action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Places",
     "Favorites ❤️",
     "Map View 🗺️",
     "Add a Place",
     "Add a Review",
     "Random Pick (with filters)",
     "Pick History 📜"]
)

# Badges
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Total Places:** {total_places}")
st.sidebar.markdown(f"**Favorites ❤️:** {favorites_count}")
st.sidebar.markdown(f"**Not Visited Yet:** {not_visited_count}")

st.sidebar.markdown("---")
with st.sidebar.expander("⚙️ Data Management"):
    if st.button("Download backup (JSON + Images)"):
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            if os.path.exists(DATA_FILE):
                zip_file.write(DATA_FILE, os.path.basename(DATA_FILE))
            else:
                zip_file.writestr("restaurants.json", json.dumps([]))
            if os.path.exists(IMAGES_DIR):
                for root, _, files in os.walk(IMAGES_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(IMAGES_DIR))
                        zip_file.write(file_path, arcname)
            # Also backup history
            if os.path.exists(HISTORY_FILE):
                zip_file.write(HISTORY_FILE, os.path.basename(HISTORY_FILE))

        zip_buffer.seek(0)
        st.download_button(
            label="📥 Download full backup (ZIP)",
            data=zip_buffer.getvalue(),
            file_name=f"chicago_restaurants_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip"
        )

    uploaded_backup = st.file_uploader("Restore backup (ZIP or JSON)", type=["json", "zip"])
    if uploaded_backup and st.button("Restore Backup", type="primary"):
        try:
            if uploaded_backup.name.endswith(".zip"):
                with zipfile.ZipFile(uploaded_backup) as z:
                    if "restaurants.json" in z.namelist():
                        data = json.loads(z.read("restaurants.json"))
                        save_data(data)
                        st.session_state.restaurants = data
                    if "pick_history.json" in z.namelist():
                        hist = json.loads(z.read("pick_history.json"))
                        save_history(hist)
                    # Extract images safely
                    for name in z.namelist():
                        if name.startswith("images/"):
                            full_path = os.path.abspath(name)
                            if os.path.commonpath([full_path, os.path.abspath(IMAGES_DIR)]) == os.path.abspath(IMAGES_DIR):
                                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                                with open(full_path, "wb") as f:
                                    f.write(z.read(name))
                st.success("Full backup restored!")
                st.balloons()
            else:
                data = json.load(uploaded_backup)
                save_data(data)
                st.session_state.restaurants = data
                st.success("Data restored (images not included)")
                st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"Restore failed: {e}")

st.sidebar.caption("Built by Alan, made for us ❤️")

def delete_restaurant(index):
    r = restaurants[index]
    if r.get("photos"):
        for p in r["photos"]:
            if os.path.exists(p):
                os.remove(p)
    del restaurants[index]
    save_data(restaurants)
    st.success(f"{r['name']} deleted.")
    st.balloons()

def toggle_favorite(idx):
    restaurants[idx]["favorite"] = not restaurants[idx].get("favorite", False)
    save_data(restaurants)

def toggle_visited(idx):
    r = restaurants[idx]
    new_visited = not r.get("visited", False)
    r["visited"] = new_visited
    if new_visited and r.get("visited_date") is None:
        r["visited_date"] = datetime.now().strftime("%B %d, %Y")
    elif not new_visited:
        r["visited_date"] = None  # optional: clear date when un-visiting
    save_data(restaurants)

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

# === ACTIONS ===

if action == "Map View 🗺️":
    st.header("🗺️ Places on Map")
    map_data = []
    for r in restaurants:
        if r.get("lat") and r.get("lng"):
            color = "red" if r.get("favorite") else ("green" if r.get("visited") else "blue")
            map_data.append({
                "lat": r["lat"],
                "lon": r["lng"],
                "name": r["name"],
                "type": "🍸" if r.get("type") == "cocktail_bar" else "🍽️",
                "favorite": "❤️" if r.get("favorite") else "",
                "visited": "✅" if r.get("visited") else ""
            })
    if map_data:
        df = pd.DataFrame(map_data)
        st.map(df, latitude="lat", longitude="lon", size=100, color=None)
        st.caption("❤️ Red = Favorite | ✅ Green = Visited | 🔵 Blue = Not Visited")
    else:
        st.info("No places with coordinates yet. Add some with full addresses!")

elif action == "Pick History 📜":
    st.header("📜 Random Pick History")
    if not pick_history:
        st.info("No picks yet — go random!")
    else:
        for entry in reversed(pick_history):
            with st.container(border=True):
                st.markdown(f"**{entry['date']}** — Picked **{entry['name']}**")
                st.caption(f"{entry['cuisine']} • {entry['price']} • {entry['location']}")

elif action in ["View All Places", "Favorites ❤️"]:
    st.header("All Places" if action == "View All Places" else "❤️ Favorites")
    st.caption(f"{len(restaurants)} place(s) total")

    display_places = [r for r in restaurants if r.get("favorite", False)] if action == "Favorites ❤️" else restaurants

    col_sort, col_search = st.columns([3, 4])
    with col_sort:
        sort_by = st.selectbox("Sort by", SORT_OPTIONS, key="sort_select")
    with col_search:
        search_term = st.text_input("🔍 Search (name, cuisine, address, notes, reviews...)", key="search_input")

    # Apply search
    if search_term:
        search_lower = search_term.lower()
        filtered = []
        for r in display_places:
            if (search_lower in r["name"].lower() or
                search_lower in r["cuisine"].lower() or
                search_lower in r["location"].lower() or
                search_lower in r.get("address", "").lower() or
                search_lower in r.get("notes", "").lower() or
                any(search_lower in rev["comment"].lower() for rev in r["reviews"])):
                filtered.append(r)
        display_places = filtered
        st.write(f"**{len(display_places)}** results for '{search_term}'")

    # Apply sorting
    if sort_by == "Name (A-Z)":
        display_places = sorted(display_places, key=lambda x: x["name"].lower())
    elif sort_by == "Recently Added":
        display_places = sorted(display_places, key=lambda x: x.get("added_index", 0), reverse=True)
    elif sort_by == "Highest Rating":
        display_places = sorted(display_places, key=lambda x: sum(rev["rating"] for rev in x["reviews"])/len(x["reviews"]) if x["reviews"] else 0, reverse=True)
    elif sort_by == "Last Visited (Newest)":
        def visited_sort_key(x):
            date_str = x.get("visited_date")
            if not date_str or not x.get("visited"): return datetime.min
            try:
                return datetime.strptime(date_str, "%B %d, %Y")
            except:
                return datetime.min
        display_places = sorted(display_places, key=visited_sort_key, reverse=True)
    elif sort_by == "Random":
        display_places = display_places.copy()
        random.shuffle(display_places)

    # Assign added_index if missing (for "Recently Added" sort)
    for i, r in enumerate(restaurants):
        if "added_index" not in r:
            r["added_index"] = i
    save_data(restaurants)

    for idx, r in enumerate(display_places):
        global_idx = restaurants.index(r)
        type_icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
        fav_icon = " ❤️" if r.get("favorite") else ""
        visited_icon = " ✅" if r.get("visited") else ""
        visited_date = f" (visited {r.get('visited_date')})" if r.get("visited_date") else ""
        review_text = ""
        if r["reviews"]:
            avg = sum(rev["rating"] for rev in r["reviews"]) / len(r["reviews"])
            review_text = f" • {avg:.1f}⭐ ({len(r['reviews'])})"

        with st.expander(f"{r['name']}{type_icon}{fav_icon}{visited_icon}{visited_date} • {r['cuisine']} • {r['price']} • {r['location']}{review_text}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**Address:** {r.get('address', 'N/A')}")
                maps_url = google_maps_link(r.get("address", ""), r["name"])
                st.markdown(f"[📍 Open in Google Maps]({maps_url})")
                if r.get("notes"):
                    st.caption(f"📝 {r['notes']}")
            with col2:
                st.button("❤️ Un/Favorite", key=f"fav_{global_idx}", on_click=toggle_favorite, args=(global_idx,))
                st.button("✅ Mark as Visited" if not r.get("visited") else "✅ Unmark Visited",
                          key=f"vis_{global_idx}", on_click=toggle_visited, args=(global_idx,))
                if st.button("Edit ✏️", key=f"edit_{global_idx}"):
                    st.session_state.editing_index = global_idx
                    st.rerun()

                # Delete confirmation
                del_key = f"del_confirm_{global_idx}"
                if del_key in st.session_state:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🗑️ Confirm Delete", key=f"confirm_del_{global_idx}", type="primary"):
                            delete_restaurant(global_idx)
                            del st.session_state[del_key]
                            st.rerun()
                    with c2:
                        if st.button("Cancel", key=f"cancel_del_{global_idx}"):
                            del st.session_state[del_key]
                            st.rerun()
                else:
                    if st.button("Delete 🗑️", key=f"del_{global_idx}", type="secondary"):
                        st.session_state[del_key] = True
                        st.rerun()

            if r.get("photos"):
                st.write("**Photos:**")
                cols = st.columns(3)
                for i, p in enumerate(r["photos"]):
                    if os.path.exists(p):
                        cols[i % 3].image(p, use_column_width=True)

            if r["reviews"]:
                st.write("**Reviews:**")
                for rev in reversed(r["reviews"]):
                    st.write(f"**{'★'*rev['rating']}{'☆'*(5-rev['rating'])}** — {rev['reviewer']} ({rev['date']})")
                    st.write(rev["comment"])
                    st.markdown("---")

    # Edit form
    if "editing_index" in st.session_state:
        edit_idx = st.session_state.editing_index
        r = restaurants[edit_idx]
        st.markdown("---")
        st.subheader(f"Editing: {r['name']}")
        with st.form("edit_form"):
            new_name = st.text_input("Name*", r["name"])
            cuisine_opt = st.selectbox("Cuisine*", CUISINES, index=CUISINES.index(r["cuisine"]) if r["cuisine"] in CUISINES else CUISINES.index("Other"))
            new_cuisine = st.text_input("Custom cuisine", r["cuisine"]) if cuisine_opt == "Other" else cuisine_opt
            new_price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
            loc_opt = st.selectbox("Neighborhood*", NEIGHBORHOODS + ["Other"], index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else len(NEIGHBORHOODS))
            new_location = st.text_input("Custom neighborhood", r["location"]) if loc_opt == "Other" else loc_opt
            new_address = st.text_input("Address*", r.get("address", ""))
            new_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"], index=0 if r.get("type") == "restaurant" else 1,
                                    format_func=lambda x: "Restaurant 🍽️" if x == "restaurant" else "Cocktail Bar 🍸")
            new_visited = st.checkbox("✅ Visited", value=r.get("visited", False))
            new_notes = st.text_area("Notes (optional)", value=r.get("notes", ""))

            # Photos handling same as before...
            st.write("**Current Photos:**")
            photos_to_del = []
            if r.get("photos"):
                cols = st.columns(3)
                for i, p in enumerate(r["photos"]):
                    if os.path.exists(p):
                        with cols[i % 3]:
                            st.image(p)
                            if st.checkbox("Delete", key=f"delp_{edit_idx}_{i}"):
                                photos_to_del.append(p)
            new_photos = st.file_uploader("Add photos", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"newp_{edit_idx}")

            col_save, col_cancel = st.columns(2)
            save = col_save.form_submit_button("Save", type="primary")
            cancel = col_cancel.form_submit_button("Cancel")

            if cancel:
                del st.session_state.editing_index
                st.rerun()

            if save:
                final_cuisine = new_cuisine.strip() if cuisine_opt == "Other" else cuisine_opt
                final_location = new_location.strip() if loc_opt == "Other" else loc_opt
                if not all([new_name, final_cuisine, final_location, new_address]):
                    st.error("Required fields missing")
                else:
                    # Geocode if address changed
                    if new_address != r.get("address", ""):
                        lat, lng = geocode_address(new_address, new_name)
                        r["lat"] = lat
                        r["lng"] = lng

                    # Photos
                    for p in photos_to_del:
                        if os.path.exists(p): os.remove(p)
                        if p in r["photos"]: r["photos"].remove(p)
                    if new_photos:
                        safe_name = "".join(c for c in new_name if c.isalnum() or c in " -_").replace(" ", "_")
                        for photo in new_photos:
                            ext = photo.name.split(".")[-1]
                            fn = f"{safe_name}_{uuid.uuid4().hex[:8]}.{ext}"
                            fp = os.path.join(IMAGES_DIR, fn)
                            with open(fp, "wb") as f:
                                f.write(photo.getbuffer())
                            r["photos"].append(fp)

                    # Update visited date
                    if new_visited and not r.get("visited"):
                        visited_date = datetime.now().strftime("%B %d, %Y")
                    else:
                        visited_date = r.get("visited_date") if new_visited else None

                    r.update({
                        "name": new_name.strip(),
                        "cuisine": final_cuisine,
                        "price": new_price,
                        "location": final_location,
                        "address": new_address.strip(),
                        "type": new_type,
                        "visited": new_visited,
                        "visited_date": visited_date,
                        "notes": new_notes.strip(),
                    })
                    save_data(restaurants)
                    st.success("Updated successfully!")
                    st.balloons()
                    del st.session_state.editing_index
                    st.rerun()

# Add a Place (similar updates)
elif action == "Add a Place":
    st.header("Add New Place")
    with st.form("add_form"):
        name = st.text_input("Name*")
        cuisine_opt = st.selectbox("Cuisine*", CUISINES)
        cuisine = st.text_input("Custom cuisine") if cuisine_opt == "Other" else cuisine_opt
        price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"])
        loc_opt = st.selectbox("Neighborhood*", NEIGHBORHOODS + ["Other"])
        location = st.text_input("Custom neighborhood") if loc_opt == "Other" else loc_opt
        address = st.text_input("Address*")
        place_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"], format_func=lambda x: "Restaurant 🍽️" if x=="restaurant" else "Cocktail Bar 🍸")
        visited = st.checkbox("✅ Already visited")
        notes = st.text_area("Notes (optional)")
        photos = st.file_uploader("Photos", type=["jpg","jpeg","png"], accept_multiple_files=True)
        submitted = st.form_submit_button("Add Place", type="primary")

        if submitted:
            final_cuisine = cuisine.strip() if cuisine_opt == "Other" else cuisine_opt
            final_location = location.strip() if loc_opt == "Other" else loc_opt
            if not all([name, final_cuisine, final_location, address]):
                st.error("Fill required fields")
            elif any(r["name"].lower() == name.lower() for r in restaurants):
                st.warning("Place exists")
            else:
                lat, lng = geocode_address(address, name)
                photo_paths = []
                if photos:
                    safe_name = "".join(c for c in name if c.isalnum() or c in " -_").replace(" ", "_")
                    for p in photos:
                        ext = p.name.split(".")[-1]
                        fn = f"{safe_name}_{uuid.uuid4().hex[:8]}.{ext}"
                        fp = os.path.join(IMAGES_DIR, fn)
                        with open(fp, "wb") as f:
                            f.write(p.getbuffer())
                        photo_paths.append(fp)

                new_place = {
                    "name": name.strip(),
                    "cuisine": final_cuisine,
                    "price": price,
                    "location": final_location,
                    "address": address.strip(),
                    "type": place_type,
                    "favorite": False,
                    "visited": visited,
                    "visited_date": datetime.now().strftime("%B %d, %Y") if visited else None,
                    "notes": notes.strip(),
                    "photos": photo_paths,
                    "reviews": [],
                    "lat": lat,
                    "lng": lng,
                    "added_index": len(restaurants)
                }
                restaurants.append(new_place)
                save_data(restaurants)
                st.success(f"{name} added!")
                st.balloons()
                st.rerun()

# Add Review and Random Pick remain mostly the same, but Random Pick now logs to history
elif action == "Add a Review":
    # ... (same as before, unchanged for brevity)

elif action == "Random Pick (with filters)":
    # ... (same filters as before)
    if st.button("🎲 Pick Random Place!", type="primary", use_container_width=True):
        choice = random.choice(filtered)
        st.session_state.last_random_choice = choice
        # Log to history
        entry = {
            "name": choice["name"],
            "cuisine": choice["cuisine"],
            "price": choice["price"],
            "location": choice["location"],
            "date": datetime.now().strftime("%B %d, %Y at %I:%M %p")
        }
        pick_history.append(entry)
        save_history(pick_history)
        st.balloons()
        st.rerun()

    # Display choice with visited toggle button too
    if "last_random_choice" in st.session_state:
        choice = st.session_state.last_random_choice
        # ... display code ...
        global_idx = restaurants.index(choice)
        col_fav, col_vis = st.columns(2)
        with col_fav:
            st.button("❤️ Un/Favorite", key=f"rand_fav_{global_idx}", on_click=toggle_favorite, args=(global_idx,))
        with col_vis:
            st.button("✅ Mark as Visited" if not choice.get("visited") else "✅ Unmark",
                      key=f"rand_vis_{global_idx}", on_click=toggle_visited, args=(global_idx,))

# (Rest of Random Pick display unchanged)
