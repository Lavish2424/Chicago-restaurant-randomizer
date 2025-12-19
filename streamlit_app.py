import streamlit as st
import json
import os
import random
import urllib.parse
import uuid
from datetime import datetime
import zipfile
from io import BytesIO
from streamlit.components.v1 import html

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

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for place in data:
                    if "favorite" not in place: place["favorite"] = False
                    if "visited" not in place: place["visited"] = False
                    if "photos" not in place: place["photos"] = []
                    if "reviews" not in place: place["reviews"] = []
                    if "added_date" not in place: place["added_date"] = datetime.now().isoformat()
                return data
        except json.JSONDecodeError:
            st.error("Data file is corrupted. Starting with empty list.")
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

st.markdown("<h1 style='text-align: center;'>🍽️ Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, favorite, and randomly pick Chicago eats & drinks! 🍸</p>", unsafe_allow_html=True)

st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?", ["View All Places", "Add a Place", "Random Pick (with filters)"])
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
                for root, _, files in os.walk(IMAGES_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=os.path.dirname(IMAGES_DIR))
                        zip_file.write(file_path, arcname)
        zip_buffer.seek(0)
        st.download_button("📥 Download full backup (ZIP)", zip_buffer.getvalue(),
                           f"chicago_restaurants_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip", "application/zip")

    uploaded_backup = st.file_uploader("Restore from backup (ZIP or JSON)", type=["json", "zip"], key="backup_uploader")
    if uploaded_backup and st.button("Restore Backup", type="primary"):
        try:
            if uploaded_backup.type == "application/zip" or uploaded_backup.name.endswith(".zip"):
                with zipfile.ZipFile(uploaded_backup, "r") as zip_file:
                    for name in zip_file.namelist():
                        if os.path.basename(name) == os.path.basename(DATA_FILE):
                            data = json.loads(zip_file.read(name))
                            save_data(data)
                            st.session_state.restaurants = data
                            break
                    for name in zip_file.namelist():
                        if name.startswith("images/") or name.startswith(IMAGES_DIR + "/"):
                            target_path = os.path.join(IMAGES_DIR, os.path.basename(name))
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, "wb") as f:
                                f.write(zip_file.read(name))
                st.success("Full backup restored!")
                st.balloons()
            else:
                data = json.load(uploaded_backup)
                save_data(data)
                st.session_state.restaurants = data
                st.success("JSON restored!")
                st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"Error: {str(e)}")

st.sidebar.caption("Built by Alan, made for us ❤️")

def delete_restaurant(index):
    r = restaurants[index]
    if r.get("photos"):
        for p in r["photos"]:
            if os.path.exists(p): os.remove(p)
    del restaurants[index]
    save_data(restaurants)
    st.success(f"{r['name']} deleted!")
    st.balloons()
    st.rerun()

def toggle_favorite(idx):
    restaurants[idx]["favorite"] = not restaurants[idx].get("favorite", False)
    save_data(restaurants)

def toggle_visited(idx):
    restaurants[idx]["visited"] = not restaurants[idx].get("visited", False)
    save_data(restaurants)

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

# Confetti function using canvas-confetti JS library (no extra install needed)
def confetti():
    html("""
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js"></script>
    <script>
    confetti({
      particleCount: 150,
      spread: 70,
      origin: { y: 0.6 },
      colors: ['#ff718d', '#fdff6c', '#80ff8d', '#8dffff', '#718dff']
    });
    </script>
    """, height=0)

# ────────────────────────────── View All Places ──────────────────────────────
if action == "View All Places":
    # (unchanged from previous version - omitted for brevity, copy from last working code)
    st.header("All Places")
    st.caption(f"{len(restaurants)} place(s)")
    if not restaurants:
        st.info("No places added yet.")
    else:
        col_search, col_sort = st.columns([5, 3])
        with col_search:
            search_term = st.text_input("🔍 Search name, cuisine, neighborhood, address", key="search_input")
        with col_sort:
            sort_option = st.selectbox("Sort by", ["A-Z (Name)", "Latest Added", "Favorites First"])

        filtered = restaurants.copy()
        if search_term:
            lower = search_term.lower()
            filtered = [r for r in filtered if lower in r["name"].lower() or
                        lower in r["cuisine"].lower() or lower in r["location"].lower() or
                        lower in r.get("address", "").lower()]

        if sort_option == "A-Z (Name)":
            sorted_places = sorted(filtered, key=lambda x: x["name"].lower())
        elif sort_option == "Latest Added":
            sorted_places = sorted(filtered, key=lambda x: x.get("added_date", ""), reverse=True)
        else:
            sorted_places = sorted([r for r in filtered if r.get("favorite")], key=lambda x: x["name"].lower()) + \
                            sorted([r for r in filtered if not r.get("favorite")], key=lambda x: x["name"].lower())

        for idx, r in enumerate(sorted_places):
            global_idx = restaurants.index(r)
            icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
            fav = " ❤️" if r.get("favorite") else ""
            visited = " ✅" if r.get("visited") else ""
            notes_count = f" • {len(r['reviews'])} note{'s' if len(r['reviews']) != 1 else ''}" if r["reviews"] else ""
            with st.expander(f"{r['name']}{icon}{fav}{visited} • {r['cuisine']} • {r['price']} • {r['location']}{notes_count}",
                             expanded=(f"edit_mode_{global_idx}" in st.session_state)):
                # (rest of View All Places unchanged - use from previous code)
                pass  # Replace with full code from earlier version

# ────────────────────────────── Add a Place ──────────────────────────────
elif action == "Add a Place":
    # (unchanged - use from previous code)
    pass  # Replace with full code from earlier version

# ────────────────────────────── Random Pick with Confetti ──────────────────────────────
else:
    st.header("🎲 Random Place Picker")
    if not restaurants:
        st.info("Add places first!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            cuisine_filter = st.multiselect("Cuisine", sorted({r["cuisine"] for r in restaurants}))
            price_filter = st.multiselect("Price", sorted({r["price"] for r in restaurants}, key=len))
            type_filter = st.selectbox("Type", ["all", "restaurant", "cocktail_bar"],
                                       format_func=lambda x: {"all":"All", "restaurant":"Restaurants 🍽️", "cocktail_bar":"Bars 🍸"}[x])
            only_fav = st.checkbox("Only favorites ❤️")
            visited_filter = st.selectbox("Visited", VISITED_OPTIONS)
        with col2:
            location_filter = st.multiselect("Neighborhood", sorted({r["location"] for r in restaurants}))

        filtered = [r for r in restaurants
                    if (not only_fav or r.get("favorite"))
                    and (type_filter == "all" or r.get("type") == type_filter)
                    and (not cuisine_filter or r["cuisine"] in cuisine_filter)
                    and (not price_filter or r["price"] in price_filter)
                    and (not location_filter or r["location"] in location_filter)
                    and (visited_filter == "All" or
                         (visited_filter == "Visited Only" and r.get("visited")) or
                         (visited_filter == "Not Visited Yet" and not r.get("visited")))]

        st.write(f"**{len(filtered)} places** match")

        if not filtered:
            st.warning("No matches – try broader filters!")
        else:
            if st.button("🎲 Pick Random Place!", type="primary", use_container_width=True):
                picked = random.choice(filtered)
                st.session_state.last_pick = picked
                confetti()      # Real colorful confetti burst!
                st.balloons()   # Keep balloons for extra fun
                st.rerun()

            if "last_pick" in st.session_state and st.session_state.last_pick in filtered:
                c = st.session_state.last_pick
                with st.container(border=True):
                    tag = " 🍸 Cocktail Bar" if c.get("type")=="cocktail_bar" else " 🍽️ Restaurant"
                    fav = " ❤️" if c.get("favorite") else ""
                    vis = " ✅ Visited" if c.get("visited") else ""
                    st.markdown(f"# {c['name']}{tag}{fav}{vis}")
                    st.write(f"{c['cuisine']} • {c['price']} • {c['location']}")
                    st.write(f"**Address:** {c.get('address','')}")
                    st.markdown(f"[📍 Google Maps]({google_maps_link(c.get('address',''), c['name'])})")

                    idx = restaurants.index(c)

                    col_fav, col_vis = st.columns(2)
                    with col_fav:
                        st.button("❤️ Unfavorite" if c.get("favorite") else "❤️ Favorite",
                                  key=f"rand_fav_{idx}", on_click=toggle_favorite, args=(idx,))
                    with col_vis:
                        st.button("✅ Mark as Unvisited" if c.get("visited") else "✅ Mark as Visited",
                                  key=f"rand_vis_{idx}", on_click=toggle_visited, args=(idx,))

                    if c.get("photos"):
                        st.markdown("### Photos")
                        cols = st.columns(3)
                        for i, p in enumerate(c["photos"]):
                            if os.path.exists(p): cols[i%3].image(p, use_column_width=True)

                    if c["reviews"]:
                        st.markdown("### Notes")
                        for rev in c["reviews"]:
                            st.write(f"**{rev['reviewer']} ({rev['date']})**")
                            st.write(f"_{rev['comment']}_")
                    else:
                        st.info("No notes yet!")

                    if st.button("🎲 Pick Again!", type="secondary", use_container_width=True):
                        picked = random.choice(filtered)
                        st.session_state.last_pick = picked
                        confetti()
                        st.balloons()
                        st.rerun()
            elif "last_pick" in st.session_state:
                st.info("Previous pick no longer matches filters – pick again!")
                if st.button("Clear previous pick"):
                    del st.session_state.last_pick
                    st.rerun()
