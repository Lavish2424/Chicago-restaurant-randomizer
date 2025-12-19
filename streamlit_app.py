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
    "Fulton Market", "River North", "Gold Coast", "South Loop",
    "Chinatown", "Pilsen", "West Town"
]

CUISINES = [
    "Chinese", "Italian", "American", "Mexican", "Japanese", "Indian", "Thai",
    "French", "Korean", "Pizza", "Burgers", "Seafood", "Steakhouse",
    "Bar Food", "Cocktails", "Other"
]

VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for place in data:
                    place.setdefault("favorite", False)
                    place.setdefault("visited", False)
                    place.setdefault("photos", [])
                    place.setdefault("reviews", [])
                    place.setdefault("added_date", datetime.now().isoformat())
                return data
        except json.JSONDecodeError:
            st.error("Data file corrupted. Starting fresh.")
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

st.markdown("<h1 style='text-align: center;'>Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, favorite, review, and randomly pick your next spot!</p>", unsafe_allow_html=True)

st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?", [
    "View All Places", "Add a Place", "Random Pick (with filters)"
])

# ==================== DATA MANAGEMENT ====================
with st.sidebar.expander("Data Management"):
    if st.button("Download backup (JSON + Images)"):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(DATA_FILE):
                zf.write(DATA_FILE)
            if os.path.exists(IMAGES_DIR):
                for root, _, files in os.walk(IMAGES_DIR):
                    for file in files:
                        zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), IMAGES_DIR))
        buffer.seek(0)
        st.download_button(
            "Download ZIP backup",
            buffer,
            f"chicago_eats_backup_{datetime.now().strftime('%Y%m%d')}.zip",
            "application/zip"
        )

    uploaded = st.file_uploader("Restore backup", type=["json", "zip"])
    if uploaded and st.button("Restore Backup", type="primary"):
        try:
            if uploaded.name.endswith(".zip"):
                with zipfile.ZipFile(uploaded) as zf:
                    if "restaurants.json" in zf.namelist():
                        data = json.loads(zf.read("restaurants.json"))
                        save_data(data)
                        st.session_state.restaurants = data
                        st.success("Restored successfully!")
                        st.balloons()
                        st.rerun()
            else:
                data = json.load(uploaded)
                save_data(data)
                st.session_state.restaurants = data
                st.success("JSON restored!")
                st.balloons()
                st.rerun()
        except Exception as e:
            st.error(f"Restore failed: {e}")

st.sidebar.caption("Made with ❤️ by Alan")

# ==================== HELPERS ====================
def delete_restaurant(idx):
    r = restaurants[idx]
    for p in r.get("photos", []):
        if os.path.exists(p):
            os.remove(p)
    del restaurants[idx]
    save_data(restaurants)
    st.success("Deleted!")
    st.balloons()

def toggle_favorite(idx):
    restaurants[idx]["favorite"] = not restaurants[idx].get("favorite", False)
    save_data(restaurants)

def google_maps_link(address, name=""):
    q = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(q)}"

# ==================== VIEW ALL PLACES ====================
if action == "View All Places":
    st.header("All Places")
    st.caption(f"{len(restaurants)} place(s) total")

    if not restaurants:
        st.info("No places yet — go add some!")
    else:
        col1, col2 = st.columns([5, 3])
        with col1:
            search = st.text_input("Search", key="search", placeholder="Name, cuisine, neighborhood...")
        with col2:
            sort_by = st.selectbox("Sort by", ["A-Z (Name)", "Latest Added", "Favorites First"], key="sort")

        # Filtering
        filtered = restaurants.copy()
        if search:
            s = search.lower()
            filtered = [r for r in filtered if any(s in str(v).lower() for v in r.values() if isinstance(v, str))]

        # Sorting
        if sort_by == "A-Z (Name)":
            filtered.sort(key=lambda x: x["name"].lower())
        elif sort_by == "Latest Added":
            filtered.sort(key=lambda x: x.get("added_date", ""), reverse=True)
        elif sort_by == "Favorites First":
            filtered.sort(key=lambda x: (not x.get("favorite", False), x["name"].lower()))

        st.write(f"**Showing {len(filtered)} place(s)**")

        for idx, r in enumerate(filtered):
            global_idx = restaurants.index(r)
            type_icon = "Cocktail Bar" if r.get("type") == "cocktail_bar" else "Restaurant"
            fav_icon = "Favorite" if r.get("favorite", False) else ""
            visited_icon = "Visited" if r.get("visited", False) else ""
            avg_rating = f"{sum(rev['rating'] for rev in r['reviews'])/len(r['reviews']):.1f} ({len(r['reviews'])})" if r["reviews"] else ""

            with st.expander(f"{r['name']} {type_icon} {fav_icon} {visited_icon} • {r['cuisine']} • {r['price']} • {r['location']} {avg_rating}", 
                           expanded=st.session_state.get(f"exp_{global_idx}", False)):
                
                # Force expand when editing
                if st.session_state.get("editing_index") == global_idx:
                    st.session_state[f"exp_{global_idx}"] = True

                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Address:** {r.get('address', '—')}")
                    st.markdown(f"[Open in Google Maps]({google_maps_link(r.get('address', ''), r['name'])})")
                with col2:
                    st.button("Unfavorite" if r.get("favorite") else "Favorite", key=f"fav_{global_idx}", on_click=toggle_favorite, args=(global_idx,))

                if r.get("photos"):
                    cols = st.columns(min(3, len(r["photos"])))
                    for i, path in enumerate(r["photos"]):
                        if os.path.exists(path):
                            cols[i % 3].image(path, use_column_width=True)

                if r["reviews"]:
                    st.write("**Reviews**")
                    for rev in reversed(r["reviews"]):
                        stars = "★" * rev["rating"] + "☆" * (5 - rev["rating"])
                        st.write(f"**{stars}** — {rev['reviewer']} ({rev['date']})")
                        st.write(rev["comment"])
                        st.markdown("---")
                else:
                    st.caption("_No reviews yet_")

                # EDIT BUTTON & IN-PLACE FORM
                if st.button("Edit", key=f"edit_btn_{global_idx}"):
                    st.session_state.editing_index = global_idx
                    st.rerun()

                if st.session_state.get("editing_index") == global_idx:
                    st.markdown("---")
                    st.subheader("Editing this place")

                    with st.form(key=f"form_{global_idx}"):
                        new_name = st.text_input("Name*", r["name"])
                        cuisine_option = st.selectbox("Cuisine*", CUISINES, index=CUISINES.index(r["cuisine"]) if r["cuisine"] in CUISINES else -1)
                        new_cuisine = st.text_input("Custom cuisine", r["cuisine"]) if cuisine_option == "Other" else cuisine_option
                        new_price = st.selectbox("Price", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
                        location_option = st.selectbox("Neighborhood*", NEIGHBORHOODS + ["Other"], index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else -1)
                        new_location = st.text_input("Custom neighborhood", r["location"]) if location_option == "Other" else location_option
                        new_address = st.text_input("Address*", r.get("address", ""))
                        new_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"], index=0 if r.get("type") != "cocktail_bar" else 1,
                                                format_func=lambda x: "Restaurant" if x == "restaurant" else "Cocktail Bar")
                        new_visited = st.checkbox("Visited", r.get("visited", False))

                        # Photos
                        st.write("**Photos (check to delete)**")
                        photos_to_delete = []
                        cols = st.columns(3)
                        for i, path in enumerate(r.get("photos", [])):
                            if os.path.exists(path):
                                with cols[i % 3]:
                                    st.image(path, use_column_width=True)
                                    if st.checkbox("Delete", key=f"delp_{global_idx}_{i}"):
                                        photos_to_delete.append(path)
                        new_photos = st.file_uploader("Add photos", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"up_{global_idx}")

                        # Reviews editing
                        st.markdown("### Reviews")
                        reviews_to_delete = []
                        for rev_i, rev in enumerate(r["reviews"]):
                            col_r, col_c = st.columns([1, 5])
                            with col_r:
                                new_rating = st.slider("Rating", 1, 5, rev["rating"], key=f"rr_{global_idx}_{rev_i}")
                            with col_c:
                                new_comment = st.text_area("Comment", rev["comment"], height=80, key=f"rc_{global_idx}_{rev_i}")
                            if st.checkbox("Delete review", key=f"delr_{global_idx}_{rev_i}"):
                                reviews_to_delete.append(rev_i)
                            # Update live
                            r["reviews"][rev_i]["rating"] = new_rating
                            r["reviews"][rev_i]["comment"] = new_comment

                        # Add new review
                        if st.checkbox("Add another review"):
                            nr_rating = st.slider("New rating", 1, 5, 5, key=f"nr_rating_{global_idx}")
                            nr_comment = st.text_area("New comment", key=f"nr_comment_{global_idx}")

                        col_save, col_cancel = st.columns(2)
                        save = col_save.form_submit_button("Save Changes", type="primary")
                        cancel = col_cancel.form_submit_button("Cancel")

                        if cancel:
                            del st.session_state.editing_index
                            st.rerun()

                        if save:
                            final_cuisine = new_cuisine.strip() or cuisine_option
                            final_location = new_location.strip() or location_option

                            if not all([new_name, final_cuisine, final_location, new_address]):
                                st.error("Fill all required fields")
                            elif new_name.lower() != r["name"].lower() and any(p["name"].lower() == new_name.lower() for p in restaurants if p != r):
                                st.error("Name already exists")
                            else:
                                # Delete photos
                                for p in photos_to_delete:
                                    if os.path.exists(p):
                                        os.remove(p)
                                    r["photos"].remove(p)
                                # Add new photos
                                if new_photos:
                                    safe_name = "".join(c for c in new_name if c.isalnum() or c in " -_").replace(" ", "_")
                                    for photo in new_photos:
                                        ext = photo.name.split(".")[-1]
                                        path = os.path.join(IMAGES_DIR, f"{safe_name}_{uuid.uuid4().hex[:8]}.{ext}")
                                        with open(path, "wb") as f:
                                            f.write(photo.getbuffer())
                                        r["photos"].append(path)
                                # Delete reviews
                                for i in sorted(reviews_to_delete, reverse=True):
                                    del r["reviews"][i]
                                # Add new review
                                if 'nr_comment' in locals() and nr_comment.strip():
                                    r["reviews"].append({
                                        "rating": nr_rating,
                                        "comment": nr_comment.strip(),
                                        "reviewer": "You",
                                        "date": datetime.now().strftime("%B %d, %Y")
                                    })

                                # Update place
                                r.update({
                                    "name": new_name.strip(),
                                    "cuisine": final_cuisine,
                                    "price": new_price,
                                    "location": final_location,
                                    "address": new_address.strip(),
                                    "type": new_type,
                                    "visited": new_visited,
                                })
                                save_data(restaurants)
                                st.success("Updated successfully!")
                                st.balloons()
                                del st.session_state.editing_index
                                st.rerun()

                # Delete place
                if st.button("Delete place", key=f"delplace_{global_idx}", type="secondary"):
                    delete_restaurant(global_idx)
                    st.rerun()

# ==================== ADD A PLACE ====================
elif action == "Add a Place":
    st.header("Add a New Place")
    with st.form("add_form", clear_on_submit=False):
        name = st.text_input("Name*", placeholder="e.g., Lou Malnati's")
        cuisine_option = st.selectbox("Cuisine/Style*", CUISINES)
        cuisine = st.text_input("Custom cuisine (if Other)", "") if cuisine_option == "Other" else cuisine_option
        price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"])
        location_option = st.selectbox("Neighborhood*", NEIGHBORHOODS + ["Other"])
        location = st.text_input("Custom neighborhood (if Other)", "") if location_option == "Other" else location_option
        address = st.text_input("Address*", placeholder="123 Main St, Chicago, IL")
        place_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"], format_func=lambda x: "Restaurant" if x == "restaurant" else "Cocktail Bar")
        visited = st.checkbox("I've already visited")

        quick_notes = st.text_area("Quick notes / first impressions (optional)", 
                                  placeholder="e.g., Best deep dish ever — get the butter crust!", height=100)

        photos = st.file_uploader("Upload photos (optional)", type=["jpg","jpeg","png"], accept_multiple_files=True)

        if st.form_submit_button("Add Place", type="primary"):
            final_cuisine = cuisine.strip() or cuisine_option
            final_location = location.strip() or location_option

            if not all([name.strip(), final_cuisine, final_location, address.strip()]):
                st.error("Please fill all required fields")
            elif any(r["name"].lower() == name.lower().strip() for r in restaurants):
                st.error("Place already exists")
            else:
                photo_paths = []
                if photos:
                    safe = "".join(c for c in name if c.isalnum() or c in " -_").replace(" ", "_")
                    for p in photos:
                        ext = p.name.split(".")[-1]
                        path = os.path.join(IMAGES_DIR, f"{safe}_{uuid.uuid4().hex[:8]}.{ext}")
                        with open(path, "wb") as f:
                            f.write(p.getbuffer())
                        photo_paths.append(path)

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
                    new_place["reviews"].append({
                        "rating": 5,
                        "comment": quick_notes.strip(),
                        "reviewer": "You",
                        "date": datetime.now().strftime("%B %d, %Y")
                    })

                restaurants.append(new_place)
                save_data(restaurants)
                st.success("Place added!" + (" Notes saved!" if quick_notes.strip() else ""))
                st.balloons()
                st.rerun()

# ==================== RANDOM PICK ====================
else:
    st.header("Random Place Picker")
    st.markdown("Apply filters, then let fate decide!")

    if not restaurants:
        st.info("Add some places first!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            cuisines = sorted({r["cuisine"] for r in restaurants})
            cuisine_f = st.multiselect("Cuisine", cuisines)
            prices = sorted({r["price"] for r in restaurants}, key=lambda x: len(x))
            price_f = st.multiselect("Price", prices)
            type_f = st.selectbox("Type", ["all", "restaurant", "cocktail_bar"], format_func=lambda x: {"all":"All", "restaurant":"Restaurants only", "cocktail_bar":"Bars only"}[x])
            fav_only = st.checkbox("Favorites only")
            visited_f = st.selectbox("Visited", VISITED_OPTIONS)
        with col2:
            locations = sorted({r["location"] for r in restaurants})
            location_f = st.multiselect("Neighborhood", locations)

        pool = restaurants.copy()
        if fav_only: pool = [r for r in pool if r.get("favorite")]
        if type_f != "all": pool = [r for r in pool if r.get("type") == type_f]
        if cuisine_f: pool = [r for r in pool if r["cuisine"] in cuisine_f]
        if price_f: pool = [r for r in pool if r["price"] in price_f]
        if location_f: pool = [r for r in pool if r["location"] in location_f]
        if visited_f == "Visited Only": pool = [r for r in pool if r.get("visited")]
        if visited_f == "Not Visited Yet": pool = [r for r in pool if not r.get("visited")]

        st.write(f"**{len(pool)} places** match your filters")

        if not pool:
            st.warning("No places match — loosen filters!")
        else:
            if st.button("Pick Random Place!", type="primary", use_container_width=True):
                choice = random.choice(pool)
                st.session_state.last_pick = choice
                st.balloons()
                st.rerun()

            if "last_pick" in st.session_state and st.session_state.last_pick in pool:
                c = st.session_state.last_pick
                st.markdown("### Your Pick Is...")
                with st.container(border=True):
                    tag = "Cocktail Bar" if c.get("type") == "cocktail_bar" else "Restaurant"
                    fav = "Favorite" if c.get("favorite") else ""
                    vis = "Visited" if c.get("visited") else ""
                    st.markdown(f"# {c['name']} {tag} {fav} {vis}")
                    st.write(f"**{c['cuisine']} • {c['price']} • {c['location']}**")
                    st.write(c.get("address", "—"))
                    st.markdown(f"[Open in Maps]({google_maps_link(c.get('address',''), c['name'])})")
                    if c.get("photos"):
                        cols = st.columns(min(3, len(c["photos"])))
                        for i, p in enumerate(c["photos"]):
                            if os.path.exists(p):
                                cols[i % 3].image(p, use_column_width=True)
                    if c["reviews"]:
                        st.write("**Recent Reviews**")
                        for rev in c["reviews"][-3:]:
                            stars = "★" * rev["rating"] + "☆" * (5-rev["rating"])
                            st.write(f"**{stars}** — {rev['reviewer']} ({rev['date']})")
                            st.write(f"_{rev['comment']}_")
                    if st.button("Pick Again!", use_container_width=True):
                        choice = random.choice(pool)
                        st.session_state.last_pick = choice
                        st.rerun()
