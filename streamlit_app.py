import streamlit as st
import json
import os
import random
import urllib.parse
import uuid
from datetime import datetime, date
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
                    if "reservations" not in place: place["reservations"] = []
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
st.markdown("<p style='text-align: center;'>Add, favorite, reserve, and randomly pick Chicago eats & drinks! 🍸</p>", unsafe_allow_html=True)

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

# ────────────────────────────── View All Places ──────────────────────────────
if action == "View All Places":
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
            stars = f" • {sum(rev['rating'] for rev in r['reviews'])/len(r['reviews']):.1f}⭐ ({len(r['reviews'])})" if r["reviews"] else ""
            resv_count = len(r.get("reservations", []))
            resv_text = f" • {resv_count} reservation(s)" if resv_count else ""

            with st.expander(f"{r['name']}{icon}{fav}{visited} • {r['cuisine']} • {r['price']} • {r['location']}{stars}{resv_text}",
                             expanded=(f"edit_mode_{global_idx}" in st.session_state)):
                if f"edit_mode_{global_idx}" not in st.session_state:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Address:** {r.get('address', 'Not provided')}")
                        st.markdown(f"[📍 Google Maps]({google_maps_link(r.get('address', ''), r['name'])})")
                    with col2:
                        st.button("❤️ Unfavorite" if r.get("favorite") else "❤️ Favorite",
                                  key=f"fav_{global_idx}", on_click=toggle_favorite, args=(global_idx,))
                        if st.button("Edit ✏️", key=f"edit_{global_idx}"):
                            st.session_state[f"edit_mode_{global_idx}"] = True
                            st.rerun()
                        delete_key = f"del_confirm_{global_idx}"
                        if delete_key in st.session_state:
                            col_del, col_can = st.columns(2)
                            with col_del: 
                                if st.button("🗑️ Confirm Delete", type="primary", key=f"conf_{global_idx}"):
                                    delete_restaurant(global_idx)
                            with col_can: 
                                if st.button("Cancel", key=f"can_{global_idx}"):
                                    del st.session_state[delete_key]
                                    st.rerun()
                        else:
                            if st.button("Delete 🗑️", key=f"del_{global_idx}"):
                                st.session_state[delete_key] = True
                                st.rerun()

                    if r.get("photos"):
                        st.write("**Photos**")
                        cols = st.columns(3)
                        for i, p in enumerate(r["photos"]):
                            if os.path.exists(p): cols[i%3].image(p, use_column_width=True)

                    if r["reviews"]:
                        st.write("**Reviews**")
                        for rev in reversed(r["reviews"]):
                            st.write(f"**{'★'*rev['rating']}{'☆'*(5-rev['rating'])}** — {rev['reviewer']} ({rev['date']})")
                            st.write(rev['comment'])
                            st.markdown("---")
                    else:
                        st.write("_No reviews yet — be the first!_")

                    # Show reservations
                    if r.get("reservations"):
                        st.write("**Reservations**")
                        for res in sorted(r["reservations"], key=lambda x: x["date"]):
                            st.write(f"📅 **{res['date']}** at {res['time']} — Party of {res['party_size']}")
                            if res.get("notes"):
                                st.write(f"_{res['notes']}_")
                            st.markdown("---")
                    else:
                        st.write("_No reservations yet_")

                else:
                    st.subheader(f"Editing: {r['name']}")
                    with st.form(key=f"edit_form_{global_idx}"):
                        new_name = st.text_input("Name*", value=r["name"])
                        new_cuisine = st.selectbox("Cuisine/Style*", CUISINES, index=CUISINES.index(r["cuisine"]) if r["cuisine"] in CUISINES else 0)
                        new_price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
                        new_location = st.selectbox("Neighborhood*", NEIGHBORHOODS, index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else 0)
                        new_address = st.text_input("Address*", value=r.get("address", ""))
                        new_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"],
                                                format_func=lambda x: "Restaurant 🍽️" if x=="restaurant" else "Cocktail Bar 🍸",
                                                index=0 if r.get("type","restaurant")=="restaurant" else 1)
                        new_visited = st.checkbox("✅ I've already visited", value=r.get("visited", False))

                        # Reviews
                        st.write("**Reviews / Notes**")
                        reviews_to_delete = []
                        for i, rev in enumerate(r["reviews"]):
                            col_rate, col_text, col_del = st.columns([1, 5, 1])
                            with col_rate:
                                new_rating = st.number_input("Rating", 1, 5, value=rev["rating"], key=f"rat_{global_idx}_{i}")
                            with col_text:
                                new_comment = st.text_area("Comment", value=rev["comment"], height=80, key=f"com_{global_idx}_{i}")
                            with col_del:
                                if st.checkbox("Delete", key=f"del_rev_{global_idx}_{i}"):
                                    reviews_to_delete.append(i)
                            rev["rating"] = new_rating
                            rev["comment"] = new_comment

                        st.write("Add new note")
                        new_rev_rating = st.slider("Rating", 1, 5, 5, key=f"newrat_{global_idx}")
                        new_rev_comment = st.text_area("Comment", height=80, key=f"newcom_{global_idx}")

                        # Reservations
                        st.write("**Reservations**")
                        res_to_delete = []
                        for i, res in enumerate(r.get("reservations", [])):
                            col1, col2, col3, col4, col_del = st.columns([2, 1.5, 1, 3, 1])
                            with col1:
                                new_date = st.date_input("Date", value=datetime.strptime(res["date"], "%Y-%m-%d").date(), key=f"resdate_{global_idx}_{i}")
                            with col2:
                                new_time = st.time_input("Time", value=datetime.strptime(res["time"], "%H:%M").time(), key=f"restime_{global_idx}_{i}")
                            with col3:
                                new_party = st.number_input("Party", 1, 20, value=res["party_size"], key=f"resparty_{global_idx}_{i}")
                            with col4:
                                new_notes = st.text_input("Notes", value=res.get("notes", ""), key=f"resnotes_{global_idx}_{i}")
                            with col_del:
                                if st.checkbox("Delete", key=f"del_res_{global_idx}_{i}"):
                                    res_to_delete.append(i)
                            # Update in place
                            res["date"] = new_date.strftime("%Y-%m-%d")
                            res["time"] = new_time.strftime("%H:%M")
                            res["party_size"] = new_party
                            res["notes"] = new_notes

                        st.write("Add new reservation")
                        add_date = st.date_input("Date", value=date.today(), key=f"adddate_{global_idx}")
                        add_time = st.time_input("Time", value=datetime.now().time(), key=f"addtime_{global_idx}")
                        add_party = st.number_input("Party size", 1, 20, value=2, key=f"addparty_{global_idx}")
                        add_notes = st.text_input("Notes (optional)", key=f"addnotes_{global_idx}")

                        # Photos
                        st.write("**Photos (check to delete)**")
                        photos_to_delete = []
                        if r.get("photos"):
                            cols = st.columns(3)
                            for i, p in enumerate(r["photos"]):
                                if os.path.exists(p):
                                    with cols[i%3]:
                                        st.image(p, use_column_width=True)
                                        if st.checkbox("Delete", key=f"del_ph_{global_idx}_{i}"):
                                            photos_to_delete.append(p)

                        new_photos = st.file_uploader("Add photos", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"new_ph_{global_idx}")

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            save_btn = st.form_submit_button("Save Changes", type="primary")
                        with col_cancel:
                            cancel_btn = st.form_submit_button("Cancel")

                        if cancel_btn:
                            del st.session_state[f"edit_mode_{global_idx}"]
                            st.rerun()

                        if save_btn:
                            if not all([new_name.strip(), new_address.strip()]):
                                st.error("Name and address required")
                            elif new_name.lower().strip() != r["name"].lower() and any(e["name"].lower() == new_name.lower().strip() for e in restaurants if e != r):
                                st.warning("Name already exists!")
                            else:
                                # Handle deletions
                                for p in photos_to_delete:
                                    if os.path.exists(p): os.remove(p)
                                    if p in r["photos"]: r["photos"].remove(p)
                                for i in sorted(reviews_to_delete + res_to_delete, reverse=True):
                                    if i < len(r["reviews"]):
                                        del r["reviews"][i]
                                    else:
                                        del r["reservations"][i - len(r["reviews"])]

                                # Add new review
                                if new_rev_comment.strip():
                                    r["reviews"].append({
                                        "rating": new_rev_rating,
                                        "comment": new_rev_comment.strip(),
                                        "reviewer": "You",
                                        "date": datetime.now().strftime("%B %d, %Y")
                                    })

                                # Add new reservation
                                r["reservations"].append({
                                    "date": add_date.strftime("%Y-%m-%d"),
                                    "time": add_time.strftime("%H:%M"),
                                    "party_size": add_party,
                                    "notes": add_notes
                                })

                                # Add photos
                                if new_photos:
                                    safe = "".join(c for c in new_name if c.isalnum() or c in " -_").replace(" ", "_")
                                    for photo in new_photos:
                                        ext = photo.name.split(".")[-1].lower()
                                        fname = f"{safe}_{uuid.uuid4().hex[:8]}.{ext}"
                                        path = os.path.join(IMAGES_DIR, fname)
                                        with open(path, "wb") as f: f.write(photo.getbuffer())
                                        r["photos"].append(path)

                                r.update({
                                    "name": new_name.strip(),
                                    "cuisine": new_cuisine,
                                    "price": new_price,
                                    "location": new_location,
                                    "address": new_address.strip(),
                                    "type": new_type,
                                    "visited": new_visited
                                })
                                save_data(restaurants)
                                st.success(f"{new_name} saved!")
                                st.balloons()
                                del st.session_state[f"edit_mode_{global_idx}"]
                                st.rerun()

# ────────────────────────────── Add a Place ──────────────────────────────
elif action == "Add a Place":
    st.header("Add a New Place")
    with st.form("add_place_form"):
        name = st.text_input("Name*")
        cuisine = st.selectbox("Cuisine/Style*", CUISINES)
        price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"])
        location = st.selectbox("Neighborhood*", NEIGHBORHOODS)
        address = st.text_input("Address*")
        place_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"],
                                  format_func=lambda x: "Restaurant 🍽️" if x=="restaurant" else "Cocktail Bar 🍸")
        visited = st.checkbox("✅ I've already visited")
        quick_notes = st.text_area("Quick notes (optional)", height=100)
        photos = st.file_uploader("Photos (optional)", type=["jpg","jpeg","png"], accept_multiple_files=True)
        if st.form_submit_button("Add Place", type="primary"):
            if not all([name.strip(), address.strip()]):
                st.error("Name and address required")
            elif any(r["name"].lower() == name.lower().strip() for r in restaurants):
                st.warning("Already exists!")
            else:
                photo_paths = []
                if photos:
                    safe = "".join(c for c in name if c.isalnum() or c in " -_").replace(" ", "_")
                    for p in photos:
                        ext = p.name.split(".")[-1].lower()
                        fname = f"{safe}_{uuid.uuid4().hex[:8]}.{ext}"
                        path = os.path.join(IMAGES_DIR, fname)
                        with open(path, "wb") as f: f.write(p.getbuffer())
                        photo_paths.append(path)

                new = {
                    "name": name.strip(), "cuisine": cuisine, "price": price, "location": location,
                    "address": address.strip(), "type": place_type, "favorite": False, "visited": visited,
                    "photos": photo_paths, "reviews": [], "reservations": [], "added_date": datetime.now().isoformat()
                }
                if quick_notes.strip():
                    new["reviews"].append({
                        "rating": 5, "comment": quick_notes.strip(), "reviewer": "You",
                        "date": datetime.now().strftime("%B %d, %Y")
                    })
                restaurants.append(new)
                save_data(restaurants)
                st.success(f"{name} added!")
                st.balloons()
                st.rerun()

# ────────────────────────────── Random Pick ──────────────────────────────
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
                st.session_state.last_pick = random.choice(filtered)
                st.balloons()
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

                    # Quick Add Reservation
                    st.markdown("### Quick Reservation")
                    with st.form(key=f"quick_res_form_{idx}"):
                        col_d, col_t = st.columns(2)
                        with col_d:
                            res_date = st.date_input("Date", value=date.today(), key=f"qdate_{idx}")
                        with col_t:
                            res_time = st.time_input("Time", value=datetime.now().time(), key=f"qtime_{idx}")
                        col_p, col_n = st.columns(2)
                        with col_p:
                            res_party = st.number_input("Party size", 1, 20, 2, key=f"qparty_{idx}")
                        with col_n:
                            res_notes = st.text_input("Notes (optional)", key=f"qnotes_{idx}")
                        if st.form_submit_button("📅 Add Reservation", type="primary"):
                            c["reservations"].append({
                                "date": res_date.strftime("%Y-%m-%d"),
                                "time": res_time.strftime("%H:%M"),
                                "party_size": res_party,
                                "notes": res_notes
                            })
                            save_data(restaurants)
                            st.success("Reservation added!")
                            st.balloons()
                            st.rerun()

                    if c.get("photos"):
                        st.markdown("### Photos")
                        cols = st.columns(3)
                        for i, p in enumerate(c["photos"]):
                            if os.path.exists(p): cols[i%3].image(p, use_column_width=True)
                    if c["reviews"]:
                        st.markdown("### Reviews")
                        for rev in c["reviews"][-3:]:
                            st.write(f"**{'★'*rev['rating']}{'☆'*(5-rev['rating'])}** — {rev['reviewer']} ({rev['date']})")
                            st.write(f"_{rev['comment']}_")
                    else:
                        st.info("No reviews yet!")
                    if st.button("🎲 Pick Again!", type="secondary", use_container_width=True):
                        st.session_state.last_pick = random.choice(filtered)
                        st.rerun()
            elif "last_pick" in st.session_state:
                st.info("Previous pick no longer matches filters – pick again!")
                if st.button("Clear previous pick"):
                    del st.session_state.last_pick
                    st.rerun()
