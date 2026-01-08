import streamlit as st
import random
import urllib.parse
from datetime import datetime, date
from supabase import create_client, Client
import os

# ==================== SUPABASE SETUP ====================
# Ensure these are set in your .streamlit/secrets.toml
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"

# ==================== CSS & UI TWEAKS ====================
st.set_page_config(page_title="Chicago Eats", page_icon="🍽️")

st.markdown("""
    <style>
    /* Make images in grid uniform and professional */
    [data-testid="stHorizontalBlock"] img {
        object-fit: cover;
        border-radius: 10px;
        height: 160px;
        width: 100%;
    }
    /* Simple card-like styling for expanders */
    .stExpander {
        border: 1px solid #f0f2f6;
        border-radius: 10px;
        margin-bottom: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# ==================== DATA CORE ====================
@st.cache_data(ttl=600)
def load_data():
    """Fetches data from Supabase and caches it for 10 minutes."""
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

def clear_cache_and_reload():
    """Call this whenever you modify the database."""
    st.cache_data.clear()
    st.session_state.restaurants = load_data()

# Initialize session state
if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

# ==================== HELPER FUNCTIONS ====================
def save_data(data_list):
    """Updates Supabase with the current state of a list of restaurants."""
    try:
        for place in data_list:
            place_id = place.get("id")
            update_data = {k: v for k, v in place.items() if k != 'id'}
            if place_id:
                supabase.table("restaurants").update(update_data).eq("id", place_id).execute()
            else:
                supabase.table("restaurants").insert(update_data).execute()
        clear_cache_and_reload()
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")

def delete_restaurant(res_id, image_urls):
    """Deletes record from DB and associated images from Storage."""
    try:
        if image_urls:
            paths_to_delete = []
            for url in image_urls:
                path = urllib.parse.urlparse(url).path
                prefix = f"/storage/v1/object/public/{BUCKET_NAME}/"
                if path.startswith(prefix):
                    paths_to_delete.append(path[len(prefix):])
            if paths_to_delete:
                supabase.storage.from_(BUCKET_NAME).remove(paths_to_delete)
        
        supabase.table("restaurants").delete().eq("id", res_id).execute()
        clear_cache_and_reload()
        st.success("Deleted successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Delete failed: {e}")

def toggle_favorite(res_id):
    # Find specific item in session state
    for r in st.session_state.restaurants:
        if r["id"] == res_id:
            new_val = not r.get("favorite", False)
            supabase.table("restaurants").update({"favorite": new_val}).eq("id", res_id).execute()
            break
    clear_cache_and_reload()
    st.rerun()

def toggle_visited(res_id):
    for r in st.session_state.restaurants:
        if r["id"] == res_id:
            new_val = not r.get("visited", False)
            update_vals = {"visited": new_val}
            if not new_val: update_vals["visited_date"] = None
            supabase.table("restaurants").update(update_vals).eq("id", res_id).execute()
            break
    clear_cache_and_reload()
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
            filename = f"{sanitized_name}_{i}_{random.randint(1000,9999)}{file_ext}"
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

# ==================== SIDEBAR ====================
st.sidebar.header("🍽️ Navigation")
action = st.sidebar.radio("Go to:", ["View All Places", "Add a Place", "Random Pick"])
st.sidebar.markdown("---")
st.sidebar.caption("Built for Alan & Co ❤️")

NEIGHBORHOODS = ["Fulton Market", "River North", "Gold Coast", "South Loop", "Chinatown", "Pilsen", "West Town", "West Loop", "Wicker Park", "Logan Square"]
CUISINES = ["American", "Asian", "Mexican", "Japanese", "Italian", "Indian", "Thai", "French", "Seafood", "Steakhouse", "Cocktails", "Other"]
VISITED_OPTIONS = ["All", "Visited Only", "Not Visited Yet"]

# ==================== MAIN CONTENT ====================
st.markdown("<h1 style='text-align: center;'>🍽️ Chicago Restaurant Tracker</h1>", unsafe_allow_html=True)

# ────────────────────────────── View All Places ──────────────────────────────
if action == "View All Places":
    st.header("All Places 👀")
    
    if not st.session_state.restaurants:
        st.info("No places added yet.")
    else:
        col_search, col_sort = st.columns([5, 3])
        with col_search:
            search_term = st.text_input("🔍 Search names, cuisines, or neighborhoods", key="search_input")
        with col_sort:
            sort_option = st.selectbox("Sort by", ["Recently Added", "A-Z (Name)", "Favorites First"])

        filtered = st.session_state.restaurants.copy()
        if search_term:
            lower = search_term.lower()
            filtered = [r for r in filtered if lower in r["name"].lower() or 
                        lower in r["cuisine"].lower() or lower in r["location"].lower()]

        # Sorting logic including the new "Recently Added"
        if sort_option == "Recently Added":
            # Sorts by ID descending (highest ID is newest)
            sorted_places = sorted(filtered, key=lambda x: x.get("id", 0), reverse=True)
        elif sort_option == "A-Z (Name)":
            sorted_places = sorted(filtered, key=lambda x: x["name"].lower())
        else:
            sorted_places = sorted([r for r in filtered if r.get("favorite")], key=lambda x: x["name"].lower()) + \
                            sorted([r for r in filtered if not r.get("favorite")], key=lambda x: x["name"].lower())

        for r in sorted_places:
            res_id = r["id"]
            icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
            fav_star = " ❤️" if r.get("favorite") else ""
            vis_check = " ✅" if r.get("visited") else ""
            
            with st.container(border=True):
                expander_title = f"{r['name']}{fav_star}{vis_check} • {r['cuisine']} • {r['location']}"
                with st.expander(expander_title):
                    if f"edit_mode_{res_id}" not in st.session_state:
                        # ACTION BUTTONS
                        b1, b2, b3, b4 = st.columns(4)
                        with b1:
                            if st.button("❤️" if not r.get("favorite") else "💔", key=f"fav_{res_id}", use_container_width=True, help="Toggle Favorite"):
                                toggle_favorite(res_id)
                        with b2:
                            if st.button("✅" if not r.get("visited") else "❌", key=f"vis_{res_id}", use_container_width=True, help="Toggle Visited"):
                                toggle_visited(res_id)
                        with b3:
                            if st.button("✏️ Edit", key=f"edit_{res_id}", use_container_width=True):
                                st.session_state[f"edit_mode_{res_id}"] = True
                                st.rerun()
                        with b4:
                            if st.button("🗑️", key=f"del_{res_id}", use_container_width=True, help="Delete"):
                                delete_restaurant(res_id, r.get("images", []))

                        st.markdown(f"**Address:** {r.get('address', 'N/A')} ([Maps Link]({google_maps_link(r.get('address'), r['name'])}))")
                        
                        if r.get("visited") and r.get("visited_date"):
                            st.caption(f"Last visited: {r['visited_date']}")
                        
                        # PHOTO GRID
                        if r.get("images"):
                            img_cols = st.columns(3)
                            for idx, url in enumerate(r["images"]):
                                with img_cols[idx % 3]:
                                    st.image(url)
                        
                        # NOTES
                        if r.get("reviews"):
                            st.markdown("---")
                            for rev in r["reviews"]:
                                st.markdown(f"**{rev['date']}**: {rev['comment']}")
                    else:
                        # EDIT FORM SIMULATION (simplified for space)
                        st.subheader(f"Edit {r['name']}")
                        with st.form(f"form_edit_{res_id}"):
                            new_name = st.text_input("Name", value=r["name"])
                            new_price = st.selectbox("Price", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
                            submitted = st.form_submit_button("Save Changes")
                            if submitted:
                                supabase.table("restaurants").update({"name": new_name, "price": new_price}).eq("id", res_id).execute()
                                del st.session_state[f"edit_mode_{res_id}"]
                                clear_cache_and_reload()
                                st.rerun()
                        if st.button("Cancel", key=f"can_{res_id}"):
                            del st.session_state[f"edit_mode_{res_id}"]
                            st.rerun()

# ────────────────────────────── Add a Place ──────────────────────────────
elif action == "Add a Place":
    st.header("Add a New Spot 📍")
    
    with st.container(border=True):
        name = st.text_input("Name*")
        col1, col2 = st.columns(2)
        with col1:
            cuisine = st.selectbox("Cuisine*", CUISINES)
            location = st.selectbox("Neighborhood*", NEIGHBORHOODS)
        with col2:
            price = st.selectbox("Price*", ["$", "$$", "$$$", "$$$$"])
            p_type = st.selectbox("Type*", ["restaurant", "cocktail_bar"], format_func=lambda x: "🍽️ Restaurant" if x=="restaurant" else "🍸 Cocktail Bar")
        
        address = st.text_input("Address*")
        visited = st.checkbox("✅ I've already been here")
        v_date = None
        if visited:
            v_date = st.date_input("When did you go?", value=date.today())
        
        uploaded_images = st.file_uploader("Upload photos", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
        notes = st.text_area("Initial thoughts/notes")

        if st.button("🚀 Add to List", type="primary", use_container_width=True):
            if not name or not address:
                st.error("Please fill in Name and Address")
            else:
                with st.status("Adding place and uploading images...", expanded=True) as status:
                    image_urls = []
                    if uploaded_images:
                        image_urls = upload_images_to_supabase(uploaded_images, name)
                    
                    new_entry = {
                        "name": name.strip(),
                        "cuisine": cuisine,
                        "price": price,
                        "location": location,
                        "address": address.strip(),
                        "type": p_type,
                        "visited": visited,
                        "visited_date": v_date.strftime("%B %d, %Y") if visited else None,
                        "images": image_urls,
                        "reviews": [{"comment": notes, "date": date.today().strftime("%B %d, %Y")}] if notes else []
                    }
                    
                    supabase.table("restaurants").insert(new_entry).execute()
                    status.update(label="Success! Added to database.", state="complete", expanded=False)
                    clear_cache_and_reload()
                    st.rerun()

# ────────────────────────────── Random Pick ──────────────────────────────
else:
    st.header("Random Picker 🎲")
    if not st.session_state.restaurants:
        st.warning("Please add some places first!")
    else:
        # Simple Filter UI
        with st.expander("Filter your options"):
            f_cuisine = st.multiselect("Cuisine", options=sorted(list(set(r["cuisine"] for r in st.session_state.restaurants))))
            f_visited = st.selectbox("Status", ["Either", "Not Visited", "Visited Only"])

        filtered_rand = [r for r in st.session_state.restaurants if
                         (not f_cuisine or r["cuisine"] in f_cuisine) and
                         (f_visited == "Either" or (f_visited == "Not Visited" and not r["visited"]) or (f_visited == "Visited Only" and r["visited"]))]

        if st.button("🎲 Pick for Me!", type="primary", use_container_width=True):
            if filtered_rand:
                pick = random.choice(filtered_rand)
                st.session_state.last_pick = pick
            else:
                st.error("No places match those filters!")

        if "last_pick" in st.session_state:
            p = st.session_state.last_pick
            st.balloons()
            with st.container(border=True):
                st.markdown(f"## {p['name']}")
                st.write(f"**{p['cuisine']} • {p['location']} • {p['price']}**")
                st.write(f"📍 {p['address']}")
                if p.get("images"):
                    st.image(p["images"][0], use_container_width=True)
                st.markdown(f"[Open in Google Maps]({google_maps_link(p['address'], p['name'])})")
