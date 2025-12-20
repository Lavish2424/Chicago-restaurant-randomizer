import streamlit as st
import json
import random
import urllib.parse
import uuid
from datetime import datetime, date
import zipfile
from io import BytesIO

from supabase import create_client, Client

# ==================== SUPABASE SETUP ====================
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

STORAGE_BUCKET = "images"  # Your public bucket name

def load_data():
    response = supabase.table("restaurants").select("*").order("added_date", desc=True).execute()
    data = response.data
    for place in data:
        place.setdefault("favorite", False)
        place.setdefault("visited", False)
        place.setdefault("photos", [])
        place.setdefault("reviews", [])
    return data

def save_place(place):
    supabase.table("restaurants").upsert(place).execute()

def delete_place(place_id):
    # Delete photos first
    response = supabase.table("restaurants").select("photos").eq("id", place_id).execute()
    if response.data:
        for url in response.data[0].get("photos", []):
            try:
                file_name = url.split("/")[-1].split("?")[0]
                supabase.storage.from_(STORAGE_BUCKET).remove(file_name)
            except:
                pass
    supabase.table("restaurants").delete().eq("id", place_id).execute()

def upload_photo(photo_file):
    photo_file.seek(0)
    file_name = f"{uuid.uuid4().hex[:12]}_{photo_file.name}"
    supabase.storage.from_(STORAGE_BUCKET).upload(file_name, photo_file.getvalue())
    return supabase.storage.from_(STORAGE_BUCKET).get_public_url(file_name)

# Load data
if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

# Track tab changes
if "last_action" not in st.session_state:
    st.session_state.last_action = None

st.markdown("<h1 style='text-align: center;'>🍽️ Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, favorite, and randomly pick Chicago eats & drinks! 🍸</p>", unsafe_allow_html=True)

st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?", ["View All Places", "Add a Place", "Random Pick (with filters)"])

# Clear edit modes and random pick on tab change
if action != st.session_state.last_action:
    keys_to_clear = [k for k in st.session_state if k.startswith("edit_mode_")]
    for k in keys_to_clear:
        del st.session_state[k]
    if action == "Random Pick (with filters)" and "last_pick" in st.session_state:
        del st.session_state.last_pick

st.session_state.last_action = action

st.sidebar.markdown("---")

with st.sidebar.expander("⚙️ Data Management"):
    if st.button("Download backup (JSON only)"):
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            json_bytes = json.dumps(restaurants, indent=4).encode('utf-8')
            zip_file.writestr("restaurants.json", json_bytes)
        zip_buffer.seek(0)
        st.download_button(
            "📥 Download JSON backup",
            zip_buffer,
            f"chicago_restaurants_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
            "application/zip"
        )

st.sidebar.caption("Built by Alan, made for us ❤️")

NEIGHBORHOODS = ["Fulton Market", "River North", "Gold Coast", "South Loop", "Chinatown", "Pilsen", "West Town", "West Loop"]
CUISINES = ["Chinese", "Italian", "American", "Mexican", "Japanese", "Indian", "Thai", "French", "Korean", "Pizza", "Burgers", "Seafood", "Steakhouse", "Bar Food", "Cocktails", "Other"]
VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]

def toggle_favorite(place_id):
    place = next(r for r in restaurants if r["id"] == place_id)
    place["favorite"] = not place.get("favorite", False)
    save_place(place)
    st.session_state.restaurants = load_data()

def toggle_visited(place_id):
    place = next(r for r in restaurants if r["id"] == place_id)
    place["visited"] = not place.get("visited", False)
    save_place(place)
    st.session_state.restaurants = load_data()

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

# ==================== View All Places ====================
if action == "View All Places":
    st.header("All Places")
    st.caption(f"{len(restaurants)} place(s)")

    if not restaurants:
        st.info("No places added yet.")
    else:
        col_search, col_sort = st.columns([5, 3])
        with col_search:
            search_term = st.text_input("🔍 Search", key="search_input")
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

        for r in sorted_places:
            icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
            fav = " ❤️" if r.get("favorite") else ""
            visited = " ✅" if r.get("visited") else ""
            notes_count = f" • {len(r['reviews'])} note{'s' if len(r['reviews']) != 1 else ''}" if r["reviews"] else ""
            added = datetime.fromisoformat(r["added_date"]).strftime("%B %d, %Y") if r["added_date"] else "Unknown"

            with st.expander(f"{r['name']}{icon}{fav}{visited} • {r['cuisine']} • {r['price']} • {r['location']}{notes_count} • Added: {added}",
                             expanded=f"edit_mode_{r['id']}" in st.session_state):
                if f"edit_mode_{r['id']}" not in st.session_state:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Address:** {r.get('address', 'Not provided')}")
                        st.markdown(f"[📍 Google Maps]({google_maps_link(r.get('address', ''), r['name'])})")
                    with col2:
                        st.button("❤️ Unfavorite" if r.get("favorite") else "❤️ Favorite",
                                  key=f"fav_{r['id']}", on_click=toggle_favorite, args=(r['id'],))
                        if st.button("Edit ✏️", key=f"edit_{r['id']}"):
                            st.session_state[f"edit_mode_{r['id']}"] = True
                            st.rerun()
                        if st.button("Delete 🗑️", key=f"del_{r['id']}"):
                            delete_place(r["id"])
                            st.session_state.restaurants = load_data()
                            st.success(f"{r['name']} deleted!")
                            st.rerun()

                    if r.get("photos"):
                        st.write("**Photos**")
                        cols = st.columns(3)
                        for i, url in enumerate(r["photos"]):
                            cols[i % 3].image(url, use_column_width=True)

                    if r["reviews"]:
                        st.write("**Notes**")
                        for rev in reversed(r["reviews"]):
                            st.write(f"**{rev['reviewer']} ({rev['date']})**")
                            st.write(rev['comment'])
                            st.markdown("---")
                    else:
                        st.write("_No notes yet — be the first!_")

                else:
                    st.subheader(f"Editing: {r['name']}")
                    with st.form(key=f"edit_form_{r['id']}"):
                        new_name = st.text_input("Name*", value=r["name"])
                        new_cuisine = st.selectbox("Cuisine/Style*", CUISINES, index=CUISINES.index(r["cuisine"]))
                        new_price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
                        new_location = st.selectbox("Neighborhood*", NEIGHBORHOODS, index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else 0)
                        new_address = st.text_input("Address*", value=r.get("address", ""))
                        new_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"],
                                                format_func=lambda x: "Restaurant 🍽️" if x=="restaurant" else "Cocktail Bar 🍸",
                                                index=0 if r.get("type")=="restaurant" else 1)
                        new_visited = st.checkbox("✅ I've already visited", value=r.get("visited", False))
                        current_date = datetime.fromisoformat(r["added_date"]).date() if r["added_date"] else date.today()
                        new_added_date = st.date_input("Date Added", value=current_date)

                        reviews_to_delete = []
                        for i, rev in enumerate(r["reviews"]):
                            col_text, col_del = st.columns([6, 1])
                            with col_text:
                                new_comment = st.text_area("Comment", value=rev["comment"], height=80, key=f"com_{r['id']}_{i}")
                            with col_del:
                                if st.checkbox("Delete", key=f"del_rev_{r['id']}_{i}"):
                                    reviews_to_delete.append(i)
                            rev["comment"] = new_comment

                        st.write("Add new note (optional)")
                        new_rev_comment = st.text_area("Comment", height=80, key=f"new_rev_{r['id']}")

                        photos_to_delete = []
                        if r.get("photos"):
                            st.write("**Photos (check to delete)**")
                            cols = st.columns(3)
                            for i, url in enumerate(r["photos"]):
                                with cols[i % 3]:
                                    st.image(url, use_column_width=True)
                                    if st.checkbox("Delete", key=f"del_ph_{r['id']}_{i}"):
                                        photos_to_delete.append(url)

                        new_photos = st.file_uploader("Add photos", type=["jpg","jpeg","png"], accept_multiple_files=True, key=f"new_ph_{r['id']}")

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            save_btn = st.form_submit_button("Save Changes", type="primary")
                        with col_cancel:
                            cancel_btn = st.form_submit_button("Cancel")

                        if cancel_btn:
                            del st.session_state[f"edit_mode_{r['id']}"]
                            st.rerun()

                        if save_btn:
                            if not new_name.strip() or not new_address.strip():
                                st.error("Name and address required.")
                            elif new_name.lower().strip() != r["name"].lower() and any(e["name"].lower() == new_name.lower().strip() for e in restaurants if e != r):
                                st.warning("Name already exists!")
                            else:
                                # Delete selected photos
                                for url in photos_to_delete:
                                    try:
                                        file_name = url.split("/")[-1].split("?")[0]
                                        supabase.storage.from_(STORAGE_BUCKET).remove(file_name)
                                    except:
                                        pass
                                    if url in r["photos"]:
                                        r["photos"].remove(url)

                                # Delete selected reviews
                                for i in sorted(reviews_to_delete, reverse=True):
                                    del r["reviews"][i]

                                # Add new review
                                if new_rev_comment.strip():
                                    r["reviews"].append({
                                        "comment": new_rev_comment.strip(),
                                        "reviewer": "You",
                                        "date": datetime.now().strftime("%B %d, %Y")
                                    })

                                # Add new photos
                                new_photo_urls = [upload_photo(p) for p in new_photos] if new_photos else []
                                r["photos"].extend(new_photo_urls)

                                # Update fields
                                r.update({
                                    "name": new_name.strip(),
                                    "cuisine": new_cuisine,
                                    "price": new_price,
                                    "location": new_location,
                                    "address": new_address.strip(),
                                    "type": new_type,
                                    "visited": new_visited,
                                    "added_date": new_added_date.isoformat()
                                })

                                save_place(r)
                                st.session_state.restaurants = load_data()
                                st.success(f"{new_name} saved!")
                                del st.session_state[f"edit_mode_{r['id']}"]
                                st.rerun()

# ==================== Add a Place ====================
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
        added_date = st.date_input("Date Added", value=date.today())
        quick_notes = st.text_area("Quick notes (optional)", height=100)
        photos = st.file_uploader("Photos (optional)", type=["jpg","jpeg","png"], accept_multiple_files=True)

        submitted = st.form_submit_button("Add Place", type="primary")
        if submitted:
            if not name.strip() or not address.strip():
                st.error("Name and address required.")
            elif any(r["name"].lower() == name.lower().strip() for r in restaurants):
                st.warning("Already exists!")
            else:
                photo_urls = [upload_photo(p) for p in photos] if photos else []

                new_place = {
                    "name": name.strip(),
                    "cuisine": cuisine,
                    "price": price,
                    "location": location,
                    "address": address.strip(),
                    "type": place_type,
                    "favorite": False,
                    "visited": visited,
                    "photos": photo_urls,
                    "reviews": [],
                    "added_date": added_date.isoformat()
                }
                if quick_notes.strip():
                    new_place["reviews"].append({
                        "comment": quick_notes.strip(),
                        "reviewer": "You",
                        "date": datetime.now().strftime("%B %d, %Y")
                    })

                supabase.table("restaurants").insert(new_place).execute()
                st.session_state.restaurants = load_data()
                st.success(f"{name.strip()} added successfully!")
                st.rerun()

# ==================== Random Pick (with filters) ====================
else:
    st.header("🎲 Random Place Picker")
    if not restaurants:
        st.info("Add some places first!")
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
                         (visited_filter == "Not Visited Yet" and not r.get("visited"))) ]

        st.write(f"**{len(filtered)} places** match your filters")

        if not filtered:
            st.warning("No places match — try loosening your filters!")
        else:
            if st.button("🎲 Pick Random Place!", type="primary", use_container_width=True):
                picked = random.choice(filtered)
                st.session_state.last_pick = picked
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

                    col_fav, col_vis = st.columns(2)
                    with col_fav:
                        st.button("❤️ Unfavorite" if c.get("favorite") else "❤️ Favorite",
                                  key=f"rand_fav_{c['id']}", on_click=toggle_favorite, args=(c['id'],))
                    with col_vis:
                        st.button("✅ Mark as Unvisited" if c.get("visited") else "✅ Mark as Visited",
                                  key=f"rand_vis_{c['id']}", on_click=toggle_visited, args=(c['id'],))

                    if c.get("photos"):
                        st.markdown("### Photos")
                        cols = st.columns(3)
                        for i, url in enumerate(c["photos"]):
                            cols[i % 3].image(url, use_column_width=True)

                    if c["reviews"]:
                        st.markdown("### Notes")
                        for rev in c["reviews"]:
                            st.write(f"**{rev['reviewer']} ({rev['date']})**")
                            st.write(f"_{rev['comment']}_")
                    else:
                        st.info("No notes yet!")

                    if st.button("🎲 Pick Again!", type="secondary", use_container_width=True):
                        st.session_state.last_pick = random.choice(filtered)
                        st.rerun()
