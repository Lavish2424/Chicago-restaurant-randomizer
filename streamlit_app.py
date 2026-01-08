import streamlit as st
import random
import urllib.parse
from datetime import datetime, date
from supabase import create_client, Client
import os

# ==================== SUPABASE SETUP ====================
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"

def load_data():
    try:
        response = supabase.table("restaurants").select("*").execute()
        data = response.data
        for place in data:
            place.setdefault("favorite", False)
            place.setdefault("visited", False)
            place.setdefault("visited_date", None) # New field
            place.setdefault("reviews", [])
            place.setdefault("images", [])
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
                "images": place.get("images", [])
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
action = st.sidebar.radio("What do you want to do?", ["View All Places", "Add a Place", "Random Pick"])
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

        # Updated sorting logic with "Recently Added"
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
                    st.write(f"**Address:** {r.get('address', 'Not provided')}")
                    st.markdown(f"[📍 Open in Google Maps]({google_maps_link(r.get('address', ''), r['name'])})")
                    st.markdown("---")
                    if r["reviews"]:
                        st.markdown("**Notes**")
                        for rev in reversed(r["reviews"]):
                            st.write(f"**{rev['reviewer']} ({rev['date']})**")
                            st.write(rev['comment'])
                            st.markdown("---")
                    else:
                        st.write("_No notes yet — be the first!_")
                    if r.get("images"):
                        st.markdown("---")
                        st.write("**Photos**")
                        for i in range(0, len(r["images"]), 3):
                            cols = st.columns(3)
                            for j, col in enumerate(cols):
                                if i + j < len(r["images"]):
                                    with col:
                                        st.image(r["images"][i + j], use_column_width=True)
                else:
                    # Edit form (unchanged)
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
                        new_visited = st.checkbox("✅ I've visited this place", value=r.get("visited", False))
                        new_visited_date = None
                        if new_visited:
                            current_visited_date = None
                            if r.get("visited_date"):
                                try:
                                    current_visited_date = datetime.strptime(r["visited_date"], "%B %d, %Y").date()
                                except:
                                    current_visited_date = date.today()
                            new_visited_date = st.date_input("Date Visited", value=current_visited_date or date.today())
                        st.write("**Current Photos**")
                        if r.get("images"):
                            images_to_delete = []
                            for img_idx, img_url in enumerate(r["images"]):
                                col_img, col_check = st.columns([3, 1])
                                with col_img: st.image(img_url, width=200)
                                with col_check:
                                    if st.checkbox("Delete", key=f"del_img_check_{global_idx}_{img_idx}"):
                                        images_to_delete.append(img_idx)
                            st.session_state[f"images_to_delete_{global_idx}"] = images_to_delete
                        else:
                            st.caption("No photos yet")
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
                        with col_save: save_btn = st.form_submit_button("Save Changes", type="primary")
                        with col_cancel: cancel_btn = st.form_submit_button("Cancel")
                        if cancel_btn:
                            del st.session_state[f"edit_mode_{global_idx}"]
                            if f"images_to_delete_{global_idx}" in st.session_state:
                                del st.session_state[f"images_to_delete_{global_idx}"]
                            st.rerun()
                        if save_btn:
                            if not all([new_name.strip(), new_address.strip()]):
                                st.error("Name and address required")
                            elif new_name.lower().strip() != r["name"].lower() and any(e["name"].lower() == new_name.lower().strip() for e in restaurants if e != r):
                                st.warning("Name already exists!")
                            else:
                                current_images = r.get("images", []).copy()
                                if f"images_to_delete_{global_idx}" in st.session_state:
                                    for img_idx in sorted(st.session_state[f"images_to_delete_{global_idx}"], reverse=True):
                                        deleted_url = current_images.pop(img_idx)
                                        try:
                                            file_path = urllib.parse.urlparse(deleted_url).path[len(f"/storage/v1/object/public/{BUCKET_NAME}/"):]
                                            supabase.storage.from_(BUCKET_NAME).remove([file_path])
                                        except:
                                            pass
                                    del st.session_state[f"images_to_delete_{global_idx}"]
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
                                visited_date_str = new_visited_date.strftime("%B %d, %Y") if new_visited and new_visited_date else None
                                r.update({
                                    "name": new_name.strip(),
                                    "cuisine": new_cuisine,
                                    "price": new_price,
                                    "location": new_location,
                                    "address": new_address.strip(),
                                    "type": new_type,
                                    "visited": new_visited,
                                    "visited_date": visited_date_str,
                                    "images": current_images
                                })
                                save_data(restaurants)
                                st.session_state.restaurants = load_data()
                                st.success(f"{new_name} saved!")
                                del st.session_state[f"edit_mode_{global_idx}"]
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
    visited_date = None
    if visited:
        visited_date = st.date_input("Date Visited", value=date.today())
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
            visited_date_str = visited_date.strftime("%B %d, %Y") if visited and visited_date else None
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
                "reviews": [],
                "images": image_urls
            }
            if quick_notes.strip():
                new["reviews"].append({
                    "comment": quick_notes.strip(),
                    "reviewer": "You",
                    "date": datetime.now().strftime("%B %d, %Y")
                })
            try:
                supabase.table("restaurants").insert(new).execute()
                st.session_state.restaurants = load_data()
                st.success(f"{name} added!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add place: {str(e)}")

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

            if "last_pick" in st.session_state and st.session_state.last_pick in filtered:
                c = st.session_state.last_pick
                st.markdown("---")
                with st.container(border=True):
                    tag = " 🍸 Cocktail Bar" if c.get("type")=="cocktail_bar" else " 🍽️ Restaurant"
                    fav = " ❤️" if c.get("favorite") else ""
                    vis = " ✅ Visited" if c.get("visited") else ""
                    vis_date = f" ({c.get('visited_date')})" if c.get("visited_date") else ""
                    st.markdown(f"# {c['name']}")
                    st.caption(f"{tag}{fav}{vis}{vis_date}")
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
                    st.markdown(f"[Open in Google Maps ↗️]({google_maps_link(c.get('address',''), c['name'])})")
                    if c["reviews"]:
                        st.markdown("### 📝 Notes")
                        for rev in c["reviews"]:
                            with st.chat_message("user"):
                                st.write(f"**{rev['date']}**")
                                st.write(rev['comment'])
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
            elif "last_pick" in st.session_state:
                st.info("Previous pick no longer matches filters – pick again!")
