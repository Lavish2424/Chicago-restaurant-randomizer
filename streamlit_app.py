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
BUCKET_NAME = "restaurant-images"

def load_data():
    try:
        response = supabase.table("restaurants").select("*").order("added_date", desc=True).execute()
        data = response.data
        for place in data:
            place.setdefault("favorite", False)
            place.setdefault("visited", False)
            place.setdefault("reviews", [])
            place.setdefault("images", [])
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

# Render sidebar radio with a key
action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Places", "Add a Place", "Random Pick (with filters)"],
    key="main_navigation"
)

# If we just added a place, switch tab AND update the radio selection
if "switch_to_view_all" in st.session_state:
    action = "View All Places"
    st.session_state.main_navigation = "View All Places"  # This fixes the highlight!
    del st.session_state.switch_to_view_all

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

# (Helper functions unchanged: delete_restaurant, toggle_favorite, etc.)

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

def upload_images_to_supabase(uploaded_files, restaurant_name):
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
                file_options={"content-type": file.type, "upsert": "true"}
            )
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
            urls.append(public_url)
        except Exception as e:
            st.error(f"Failed to upload {file.name}: {str(e)}")
    return urls

# ────────────────────────────── View All Places ──────────────────────────────
if action == "View All Places":
    st.header("All Places")

    # Green confirmation banner after adding
    if "last_added_name" in st.session_state:
        name = st.session_state.last_added_name
        st.success(f"🎉 Great! **{name}** was added successfully!")
        # Optional: remove banner on next interaction
        # del st.session_state.last_added_name

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
            img_count = f" • {len(r.get('images', []))} photo{'s' if len(r.get('images', [])) > 1 else ''}" if r.get("images") else ""
            notes_count = f" • {len(r['reviews'])} note{'s' if len(r['reviews']) != 1 else ''}" if r["reviews"] else ""

            # REMOVED: No more 🆕 tag

            with st.expander(f"{r['name']}{icon}{fav}{visited} • {r['cuisine']} • {r['price']} • {r['location']}{img_count}{notes_count}",
                             expanded=(f"edit_mode_{global_idx}" in st.session_state)):
                # Rest of expander content (images, buttons, notes, edit form) unchanged
                if r.get("images"):
                    cols = st.columns(min(3, len(r["images"])))
                    for img_url, col in zip(r["images"], cols):
                        with col:
                            st.image(img_url, use_column_width=True)
                # ... (rest of your original expander code)

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

                    # Store name for banner and trigger tab switch
                    st.session_state.last_added_name = name.strip()
                    st.session_state.switch_to_view_all = True
                    st.rerun()

                except Exception as e:
                    st.error(f"Failed to add place: {str(e)}")

# ────────────────────────────── Random Pick ──────────────────────────────
else:
    # Your full random picker code (unchanged)
    st.header("🎲 Random Place Picker")
    # ... rest of code
