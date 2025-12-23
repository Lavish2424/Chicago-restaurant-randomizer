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

# ==================== DATA MANAGEMENT SECTION ====================
st.sidebar.subheader("💾 Data Management")

# ---- Download ZIP Backup ----
st.sidebar.markdown("**Local Backup (JSON + Photos)**")
if st.sidebar.button("📦 Create & Download ZIP Backup", use_container_width=True):
    with st.spinner("Creating backup... downloading images..."):
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add JSON
            json_str = json.dumps(restaurants, indent=2, ensure_ascii=False)
            zip_file.writestr("restaurants.json", json_str.encode('utf-8'))

            # Add images
            for place in restaurants:
                sanitized_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in place["name"])
                for idx, img_url in enumerate(place.get("images", [])):
                    try:
                        response = requests.get(img_url, timeout=15)
                        if response.status_code == 200:
                            # Try to get original extension
                            ext = os.path.splitext(urllib.parse.urlparse(img_url).path)[1]
                            if ext.lower() not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                                ext = ".jpg"
                            filename = f"{sanitized_name}_{idx}{ext}"
                            zip_path = f"images/{sanitized_name}/{filename}"
                            zip_file.writestr(zip_path, response.content)
                    except Exception as e:
                        st.warning(f"Could not download image {img_url}: {e}")

        zip_buffer.seek(0)
        st.session_state.zip_backup = zip_buffer  # Store for download button

if "zip_backup" in st.session_state:
    st.sidebar.download_button(
        label="⬇️ Download chicago_restaurants_backup.zip",
        data=st.session_state.zip_backup,
        file_name=f"chicago_restaurants_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
        mime="application/zip",
        use_container_width=True
    )
    st.sidebar.success("✅ ZIP backup ready!")

# ---- Restore from ZIP ----
st.sidebar.markdown("**Restore from Backup**")
uploaded_zip = st.sidebar.file_uploader("Upload a previous ZIP backup", type=["zip"])

if uploaded_zip is not None:
    if st.sidebar.button("🔄 Restore from Uploaded ZIP", type="primary", use_container_width=True):
        with st.spinner("Restoring backup... this may take a minute"):
            try:
                zip_bytes = io.BytesIO(uploaded_zip.getvalue())
                with zipfile.ZipFile(zip_bytes, "r") as zip_file:
                    # Extract JSON
                    if "restaurants.json" not in zip_file.namelist():
                        st.error("Invalid backup: missing restaurants.json")
                    else:
                        json_str = zip_file.read("restaurants.json").decode('utf-8')
                        restored_data = json.loads(json_str)

                        # Clear current data first
                        current_ids = [r.get("id") for r in restaurants if r.get("id")]
                        if current_ids:
                            supabase.table("restaurants").delete().in_("id", current_ids).execute()
                            # Also clear storage (optional: could be more targeted)
                            # supabase.storage.from_(BUCKET_NAME).remove(...)  # be careful!

                        new_restaurants = []
                        for place in restored_data:
                            images = place.get("images", [])
                            new_image_urls = []

                            # Re-upload images
                            sanitized_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in place["name"])
                            for idx, old_url in enumerate(images):
                                # Find image in ZIP
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

                            # Update place with new image URLs
                            place["images"] = new_image_urls
                            # Insert into database
                            response = supabase.table("restaurants").insert(place).execute()
                            inserted = response.data[0] if response.data else {}
                            new_restaurants.append(inserted)

                        # Reload session state
                        st.session_state.restaurants = new_restaurants
                        st.success("✅ Backup successfully restored!")
                        st.rerun()

            except Exception as e:
                st.error(f"Restore failed: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")

# ==================== REST OF YOUR APP (unchanged) ====================
NEIGHBORHOODS = ["Fulton Market", "River North", "Gold Coast", "South Loop", "Chinatown", "Pilsen", "West Town", "West Loop"]
CUISINES = ["American", "Asian", "Mexican", "Japanese", "Italian", "Indian", "Thai", "French", "Seafood", "Steakhouse", "Cocktails", "Other"]
VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]

# ... (all your existing functions and sections below remain exactly the same)
# delete_restaurant, toggle_favorite, toggle_visited, google_maps_link, upload_images_to_supabase,
# View All Places, Add a Place, Random Pick — no changes needed.
