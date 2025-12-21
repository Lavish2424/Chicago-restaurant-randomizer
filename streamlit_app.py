import streamlit as st
import random
import urllib.parse
from datetime import datetime, timedelta
from supabase import create_client, Client
import os

# ==================== CUSTOM CSS FOR GREEN BANNER ====================
st.markdown("""
    <style>
    .success-banner {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        text-align: center;
        font-size: 1.5rem;
        font-weight: bold;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# ==================== SUPABASE SETUP ====================
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"

# ... (your existing functions: load_data, save_data, delete_restaurant, etc. remain unchanged)

# Load data into session state
if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

# ==================== GREEN CONFIRMATION BANNER DISPLAY ====================
# Show banner for 5 seconds after successful add
if "add_success_time" in st.session_state:
    if datetime.now() - st.session_state.add_success_time < timedelta(seconds=5):
        success_msg = st.session_state.get("add_success_message", "Place added successfully!")
        st.markdown(f'<div class="success-banner">✅ {success_msg}</div>', unsafe_allow_html=True)
    else:
        # Auto-clear after 5 seconds
        del st.session_state.add_success_time
        del st.session_state.add_success_message

st.markdown("<h1 style='text-align: center;'>🍽️ Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, favorite, and randomly pick Chicago eats & drinks! 🍸</p>", unsafe_allow_html=True)

# ... (rest of your sidebar and actions code unchanged until "Add a Place")

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
        if st.form_submit_button("Add Place", type="primary"):
            if not all([name.strip(), address.strip()]):
                st.error("Name and address required")
            elif any(r["name"].lower() == name.lower().strip() for r in restaurants):
                st.warning("Already exists!")
            else:
                image_urls = []
                if uploaded_images:
                    with st.spinner("Uploading images..."):
                        image_urls = upload_images_to_supabase(uploaded_images, name)
                new = {
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
                    new["reviews"].append({
                        "comment": quick_notes.strip(),
                        "reviewer": "You",
                        "date": datetime.now().strftime("%B %d, %Y")
                    })
                try:
                    supabase.table("restaurants").insert(new).execute()
                    st.session_state.restaurants = load_data()

                    # === SET SUCCESS BANNER ===
                    photo_text = f"{len(image_urls)} photo{'s' if len(image_urls) > 1 else ''}" if image_urls else "no photos"
                    st.session_state.add_success_time = datetime.now()
                    st.session_state.add_success_message = f"{name} added successfully with {photo_text}!"

                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add place: {str(e)}")

# ... (rest of your code remains exactly the same)
