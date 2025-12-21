import streamlit as st
import random
import urllib.parse
from datetime import datetime
from supabase import create_client, Client
import os

# ==================== SUPABASE SETUP ====================
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"  # Make sure this public bucket exists in Supabase

def load_data():
    try:
        response = supabase.table("restaurants").select("*").order("added_date", desc=True).execute()
        data = response.data
        for place in data:
            place.setdefault("favorite", False)
            place.setdefault("visited", False)
            place.setdefault("reviews", [])
            place.setdefault("images", [])  # Ensure images list exists
            if "added_date" not in place:
                place["added_date"] = datetime.now().isoformat()
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
                "reviews": place["reviews"],
                "images": place.get("images", []),
                "added_date": place.get("added_date")
            }
            if place_id:
                supabase.table("restaurants").update(update_data).eq("id", place_id).execute()
            else:
                supabase.table("restaurants").insert(update_data).execute()
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")

# Load data into session state
if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

st.markdown("<h1 style='text-align: center;'>🍽️ Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, favorite, and randomly pick Chicago eats & drinks! 🍸</p>", unsafe_allow_html=True)

st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?", ["View All Places", "Add a Place", "Random Pick (with filters)"])
st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")

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

def delete_restaurant(index):
    r = restaurants[index]
   
    # Delete associated images from Supabase Storage if any
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
            except Exception as e:
                st.error(f"Error parsing image URL {url}: {str(e)}")
       
        if paths_to_delete:
            try:
                supabase.storage.from_(BUCKET_NAME).remove(paths_to_delete)
            except Exception as e:
                st.error(f"Failed to delete some images from storage: {str(e)}")
   
    # Delete the row from the database
    if "id" in r:
        supabase.table("restaurants").delete().eq("id", r["id"]).execute()
   
    del restaurants[index]
    st.session_state.restaurants = load_data()
    img_count = len(r.get("images", []))
    st.success(f"🎉 **{name}** successfully added!{photo_text}")
    st.balloons()
    st.write("🧪 TEST: If you see this, the success worked!")  # ← ADD THIS LINE
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
    """Upload images and return list of public URLs"""
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
                file_options={
                    "content-type": file.type,
                    "upsert": "true"
                }
            )
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            urls.append(public_url)
        except Exception as e:
            st.error(f"Failed to upload {file.name}: {str(e)}")
    return urls

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
                        lower in r["cuisine"].lower() or lower in r.get("location", "").lower() or
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
            img_count = f" • {len(r.get('images', []))} photo{'s' if len(r.get('images', [])) > 1 else ''}" if r.get("images") else ""
            notes_count = f" • {len(r['reviews'])} note{'s' if len(r['reviews']) != 1 else ''}" if r["reviews"] else ""
            with st.expander(f"{r['name']}{icon}{fav}{visited} • {r['cuisine']} • {r['price']} • {r['location']}{img_count}{notes_count}",
                             expanded=(f"edit_mode_{global_idx}" in st.session_state)):
              
                if r.get("images"):
                    cols = st.columns(min(3, len(r["images"])))
                    for img_url, col in zip(r["images"], cols):
                        with col:
                            st.image(img_url, use_column_width=True)
                if f"edit_mode_{global_idx}" not in st.session_state:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Address:** {r.get('address', 'Not provided')}")
                        st.markdown(f"[📍 Google Maps]({google_maps_link(r.get('address', ''), r['name'])})")
                    with col2:
                        if st.button("❤️ Unfavorite" if r.get("favorite") else "❤️ Favorite",
                                     key=f"fav_{global_idx}"):
                            toggle_favorite(global_idx)
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
                    with st.form(key=f"edit_form_{global_idx}"):
                        new_name = st.text_input("Name*", value=r["name"])
                        new_cuisine = st.selectbox("Cuisine/Style*", CUISINES, index=CUISINES.index(r["cuisine"]))
                        new_price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
                        new_location = st.selectbox("Neighborhood*", NEIGHBORHOODS, index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else 0)
                        new_address = st.text_input("Address*", value=r.get("address", ""))
                        new_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"],
                                                format_func=lambda x: "Restaurant 🍽️" if x=="restaurant" else "Cocktail Bar 🍸",
                                                index=0 if r.get("type")=="restaurant" else 1)
                        new_visited = st.checkbox("✅ I've already visited", value=r.get("visited", False))
                        st.write("**Current Photos**")
                        if r.get("images"):
                            for img_url in r["images"]:
                                st.image(img_url, width=200)
                        st.write("**Upload New Photos**")
                        new_uploaded = st.file_uploader("Add more images", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True, key=f"upload_edit_{global_idx}")
                        st.write("**Notes**")
                        reviews_to_delete = []
                        for i, rev in enumerate(r["reviews"]):
                            col_text, col_del = st.columns([6, 1])
                            with col_text:
                                new_comment = st.text_area("Comment", value=rev["comment"], height=80, key=f"com_{global_idx}_{i}")
                            with col_del:
                                if st.checkbox("Delete", key=f"del_rev_{global_idx}_{i}"):
                                    reviews_to_delete.append(i)
                            rev["comment"] = new_comment
                        st.write("Add new note (optional)")
                        new_rev_comment = st.text_area("Comment", height=80, key=f"new_rev_{global_idx}")
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
                                current_images = r.get("images", [])
                                if new_uploaded:
                                    new_urls = upload_images_to_supabase(new_uploaded, new_name)
                                    current_images.extend(new_urls)
                                for i in sorted(reviews_to_delete, reverse=True):
                                    del r["reviews"][i]
                                if new_rev_comment.strip():
                                    r["reviews"].append({
                                        "comment": new_rev_comment.strip(),
                                        "reviewer": "You",
                                        "date": datetime.now().strftime("%B %d, %Y")
                                    })
                                r.update({
                                    "name": new_name.strip(),
                                    "cuisine": new_cuisine,
                                    "price": new_price,
                                    "location": new_location,
                                    "address": new_address.strip(),
                                    "type": new_type,
                                    "visited": new_visited,
                                    "images": current_images
                                })
                                save_data(restaurants)
                                st.session_state.restaurants = load_data()
                                
                                # Celebratory success message
                                img_count = len(new_uploaded) if new_uploaded else 0
                                photo_text = f" and {img_count} new photo{'s' if img_count != 1 else ''}" if img_count else ""
                                st.success(f"🎉 **{new_name}** successfully updated!{photo_text}")
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
        uploaded_images = st.file_uploader("Upload photos", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
        quick_notes = st.text_area("Quick notes (optional)", height=100)

        submitted = st.form_submit_button("Add Place", type="primary")

        if submitted:
            if not name.strip() or not address.strip():
                st.error("Name and address are required.")
                st.stop()

            if any(r["name"].lower() == name.lower().strip() for r in restaurants):
                st.warning("A place with this name already exists!")
                st.stop()

            image_urls = []
            if uploaded_images:
                with st.spinner("Uploading photos…"):
                    image_urls = upload_images_to_supabase(uploaded_images, name)

            new_place = {
                "name": name.strip(),
                "cuisine": cuisine,
                "price": price,
                "location": location,
                "address": address.strip(),
                "type": place_type,
                "favorite": False,
                "visited": visited,
                "reviews": [],
                "images": image_urls,
                "added_date": datetime.now().isoformat()
            }
            if quick_notes.strip():
                new_place["reviews"].append({
                    "comment": quick_notes.strip(),
                    "reviewer": "You",
                    "date": datetime.now().strftime("%B %d, %Y")
                })

            try:
                response = supabase.table("restaurants").insert(new_place).execute()
                if response.data:
                    st.session_state.restaurants = load_data()
                    img_count = len(image_urls)
                    photo_text = f" with {img_count} photo{'s' if img_count != 1 else ''}" if img_count else ""
                    st.success(f"🎉 **{name}** successfully added!{photo_text}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Insert failed – no data returned. Check your table policies.")
            except Exception as e:
                st.error(f"Failed to save to database: {str(e)}")

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
                    if c.get("images"):
                        for img in c["images"]:
                            st.image(img, use_column_width=True)
                    else:
                        st.caption("No photos yet 📸")
                    st.write(f"{c['cuisine']} • {c['price']} • {c['location']}")
                    st.write(f"**Address:** {c.get('address','')}")
                    st.markdown(f"[📍 Google Maps]({google_maps_link(c.get('address',''), c['name'])})")
                    idx = restaurants.index(c)
                    col_fav, col_vis = st.columns(2)
                    with col_fav:
                        if st.button("❤️ Unfavorite" if c.get("favorite") else "❤️ Favorite",
                                     key=f"rand_fav_{idx}"):
                            toggle_favorite(idx)
                    with col_vis:
                        if st.button("✅ Mark as Unvisited" if c.get("visited") else "✅ Mark as Visited",
                                     key=f"rand_vis_{idx}"):
                            toggle_visited(idx)
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
                        st.rerun()
            elif "last_pick" in st.session_state:
                st.info("Previous pick no longer matches filters – pick again!")
                if st.button("Clear previous pick"):
                    del st.session_state.last_pick
                    st.rerun()
