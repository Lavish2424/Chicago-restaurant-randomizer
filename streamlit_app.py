import streamlit as st
import random
import urllib.parse
from datetime import datetime, date
from supabase import create_client, Client
import os
import io
import zipfile
import json
import requests  # For downloading images during backup

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
            place.setdefault("visited_date", None)
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

# ==================== SIDEBAR ====================
st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?", ["View All Places", "Add a Place", "Random Pick"])

st.sidebar.markdown("---")

# ==================== DATA MANAGEMENT (COLLAPSED EXPANDER) ====================
with st.sidebar.expander("💾 Data Management", expanded=False):
    # ---- Download ZIP Backup ----
    st.markdown("**Local Backup (JSON + Photos)**")
    if st.button("📦 Create & Download ZIP Backup", use_container_width=True):
        with st.spinner("Creating backup — downloading images..."):
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                # Add JSON data
                json_str = json.dumps(restaurants, indent=2, ensure_ascii=False)
                zip_file.writestr("restaurants.json", json_str.encode('utf-8'))

                # Add images
                for place in restaurants:
                    sanitized_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in place["name"])
                    for idx, img_url in enumerate(place.get("images", [])):
                        try:
                            response = requests.get(img_url, timeout=15)
                            if response.status_code == 200:
                                ext = os.path.splitext(urllib.parse.urlparse(img_url).path)[1]
                                if ext.lower() not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                                    ext = ".jpg"
                                filename = f"{sanitized_name}_{idx}{ext}"
                                zip_path = f"images/{sanitized_name}/{filename}"
                                zip_file.writestr(zip_path, response.content)
                        except Exception as e:
                            st.warning(f"Could not download image {img_url}: {e}")

            zip_buffer.seek(0)
            st.session_state.zip_backup = zip_buffer  # Store for download

    if "zip_backup" in st.session_state:
        st.download_button(
            label="⬇️ Download chicago_restaurants_backup.zip",
            data=st.session_state.zip_backup,
            file_name=f"chicago_restaurants_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip",
            use_container_width=True
        )
        st.success("✅ ZIP backup ready!")

    st.markdown("---")

    # ---- Restore from ZIP ----
    st.markdown("**Restore from Backup**")
    uploaded_zip = st.file_uploader("Upload a previous ZIP backup", type=["zip"], label_visibility="collapsed")

    if uploaded_zip is not None:
        if st.button("🔄 Restore from Uploaded ZIP (overwrites everything!)", type="primary", use_container_width=True):
            with st.spinner("Restoring backup — this may take a while..."):
                try:
                    zip_bytes = io.BytesIO(uploaded_zip.getvalue())
                    with zipfile.ZipFile(zip_bytes, "r") as zip_file:
                        if "restaurants.json" not in zip_file.namelist():
                            st.error("Invalid backup: missing restaurants.json")
                        else:
                            json_str = zip_file.read("restaurants.json").decode('utf-8')
                            restored_data = json.loads(json_str)

                            # Delete all current restaurants
                            current_ids = [r.get("id") for r in restaurants if r.get("id")]
                            if current_ids:
                                supabase.table("restaurants").delete().in_("id", current_ids).execute()

                            new_restaurants = []
                            for place in restored_data:
                                images = place.get("images", [])
                                new_image_urls = []

                                sanitized_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in place["name"])
                                for idx, old_url in enumerate(images):
                                    ext = os.path.splitext(urllib.parse.urlparse(old_url).path)[1] or ".jpg"
                                    filename = f"{sanitized_name}_{idx}{ext}"
                                    zip_path = f"images/{sanitized_name}/{filename}"
                                    if zip_path in zip_file.namelist():
                                        img_data = zip_file.read(zip_path)
                                        file_path = f"{sanitized_name}/{filename}"
                                        supabase.storage.from_(BUCKET_NAME).upload(
                                            path=file_path,
                                            file=img_data,
                                            file_options={"content-type": "image/jpeg", "upsert": True}
                                        )
                                        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
                                        new_image_urls.append(public_url)

                                # Update images list with new URLs
                                place["images"] = new_image_urls

                                # Insert restored place
                                response = supabase.table("restaurants").insert(place).execute()
                                inserted = response.data[0] if response.data else place  # fallback
                                new_restaurants.append(inserted)

                            st.session_state.restaurants = new_restaurants
                            st.success("✅ Backup successfully restored!")
                            st.rerun()

                except Exception as e:
                    st.error(f"Restore failed: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")

# ==================== REST OF YOUR ORIGINAL CODE (UNCHANGED) ====================
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
            sort_option = st.selectbox("Sort by", ["A-Z (Name)", "Favorites First"])
        filtered = restaurants.copy()
        if search_term:
            lower = search_term.lower()
            filtered = [r for r in filtered if lower in r["name"].lower() or
                        lower in r["cuisine"].lower() or lower in r["location"].lower() or
                        lower in r.get("address", "").lower()]
        if sort_option == "A-Z (Name)":
            sorted_places = sorted(filtered, key=lambda x: x["name"].lower())
        else:
            sorted_places = sorted([r for r in filtered if r.get("favorite")], key=lambda x: x["name"].lower()) + \
                            sorted([r for r in filtered if not r.get("favorite")], key=lambda x: x["name"].lower())
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
                    # (Your full editing form code remains unchanged – omitted here for brevity but keep it exactly as you had)
                    pass  # Replace with your original edit form code

# ────────────────────────────── Add a Place ──────────────────────────────
elif action == "Add a Place":
    # (Your full "Add a Place" form code remains unchanged)
    pass  # Replace with your original code

# ────────────────────────────── Random Pick ──────────────────────────────
else:
    # (Your full "Random Pick" code remains unchanged)
    pass  # Replace with your original code
