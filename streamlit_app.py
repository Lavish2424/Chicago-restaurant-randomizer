import streamlit as st
import random
import urllib.parse
from datetime import datetime, date
from supabase import create_client, Client
import os
import io
import zipfile
import requests  # For downloading images

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

# NEW: Function to create ZIP backup
def create_zip_backup():
    restaurants = st.session_state.restaurants
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Add JSON data
        import json
        json_data = json.dumps(restaurants, indent=2, ensure_ascii=False).encode('utf-8')
        zip_file.writestr("restaurants.json", json_data)
        
        # Add images
        for idx, place in enumerate(restaurants):
            place_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in place["name"])
            folder = f"images/{place_name}"
            for img_idx, img_url in enumerate(place.get("images", [])):
                try:
                    response = requests.get(img_url, timeout=10)
                    if response.status_code == 200:
                        # Extract original extension if possible, fallback to .jpg
                        ext = os.path.splitext(urllib.parse.urlparse(img_url).path)[1]
                        if not ext or ext.lower() not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                            ext = ".jpg"
                        filename = f"{place_name}_{img_idx}{ext}"
                        zip_file.writestr(f"{folder}/{filename}", response.content)
                except Exception as e:
                    st.warning(f"Could not download image {img_url}: {str(e)}")
    
    zip_buffer.seek(0)
    return zip_buffer

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
st.sidebar.subheader("💾 Data Management")

# Existing Save button
if st.sidebar.button("💾 Save All Changes Now", type="primary", use_container_width=True):
    with st.spinner("Saving to cloud..."):
        save_data(restaurants)
        st.session_state.restaurants = load_data()
    st.success("✅ All changes saved to Supabase!")

# NEW: Download ZIP Backup button
st.sidebar.markdown("---")
st.sidebar.caption("**Local Backup**")
if st.sidebar.button("📦 Download Backup as ZIP", type="secondary", use_container_width=True):
    with st.spinner("Creating ZIP backup with all data & photos..."):
        zip_file = create_zip_backup()
    
    st.sidebar.success("✅ Backup ready!")
    st.download_button(
        label="⬇️ Download chicago_restaurants_backup.zip",
        data=zip_file,
        file_name=f"chicago_restaurants_backup_{datetime.now().strftime('%Y%m%d')}.zip",
        mime="application/zip",
        use_container_width=True
    )

st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")

# ... (rest of your original code continues unchanged below)
# Keep everything else exactly as it was: View All Places, Add a Place, Random Pick, etc.
