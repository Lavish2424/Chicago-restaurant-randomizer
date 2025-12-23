import streamlit as st
import random
import urllib.parse
from datetime import datetime, date
from supabase import create_client, Client
import os

# ==================== SUPABASE SETUP ====================
# Ensure you have these in your .streamlit/secrets.toml
try:
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_ANON_KEY"]
except:
    st.error("Supabase secrets not found. Please check .streamlit/secrets.toml")
    st.stop()

supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"

# ==================== HELPER FUNCTIONS ====================

def load_data():
    """Fetches all data from Supabase."""
    try:
        response = supabase.table("restaurants").select("*").execute()
        data = response.data
        # Set defaults to avoid KeyErrors later
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

def update_place_in_db(place):
    """Updates a single restaurant record in Supabase efficiently."""
    try:
        place_id = place.get("id")
        if not place_id:
            st.error("Cannot update: Missing ID")
            return

        # Prepare payload (ensure date is string)
        update_payload = {
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
        
        supabase.table("restaurants").update(update_payload).eq("id", place_id).execute()
        
        # Update session state locally to reflect changes immediately
        for i, r in enumerate(st.session_state.restaurants):
            if r["id"] == place_id:
                st.session_state.restaurants[i] = place
                break
                
    except Exception as e:
        st.error(f"Error updating place: {str(e)}")

def get_storage_path(url):
    """Robustly extracts storage path from a full URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        # Splits URL at the bucket name to get the relative path
        parts = parsed.path.split(f"/{BUCKET_NAME}/")
        if len(parts) > 1:
            return parts[1]
    except:
        return None
    return None

def delete_images_from_storage(urls):
    """Deletes a list of image URLs from Supabase storage."""
    paths_to_delete = []
    for url in urls:
        path = get_storage_path(url)
        if path:
            paths_to_delete.append(path)
    
    if paths_to_delete:
        try:
            supabase.storage.from_(BUCKET_NAME).remove(paths_to_delete)
        except Exception as e:
            st.error(f"Error deleting images: {e}")

def upload_images_to_supabase(uploaded_files, restaurant_name):
    """Uploads files and returns list of public URLs."""
    urls = []
    sanitized_name = "".join(c for c in restaurant_name if c.isalnum() or c in " -_").strip().replace(" ", "_")
    
    for i, file in enumerate(uploaded_files):
        try:
            file_ext = os.path.splitext(file.name)[1].lower()
            timestamp = int(datetime.now().timestamp())
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

def parse_date_str(date_str):
    """Safely converts a string to a date object."""
    if not date_str: return date.today()
    try:
        return datetime.strptime(date_str, "%B %d, %Y").date()
    except:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            return date.today()

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

# ==================== CONSTANTS & INIT ====================

NEIGHBORHOODS = ["Fulton Market", "River North", "Gold Coast", "South Loop", "Chinatown", "Pilsen", "West Town", "West Loop", "Lincoln Park", "Wicker Park", "Logan Square"]
CUISINES = ["American", "Asian", "Mexican", "Japanese", "Italian", "Indian", "Thai", "French", "Seafood", "Steakhouse", "Cocktails", "Pizza", "Other"]

if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

st.markdown("<h1 style='text-align: center;'>🍽️🍸 Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, view, and randomly pick Chicago eats & drinks!</p>", unsafe_allow_html=True)

st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?", ["View All Places", "Add a Place", "Random Pick"])
st.sidebar.markdown("---")
st.sidebar.caption("Built with Streamlit & Supabase")

# ==================== COMPONENT: RESTAURANT CARD (FRAGMENT) ====================

@st.fragment
def render_place_card(r, index):
    """
    Renders a single restaurant card. 
    Using st.fragment ensures interactions here don't reload the whole page.
    """
    # Unique keys for widgets based on ID
    uid = r['id']
    
    icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
    fav = " ❤️" if r.get("favorite") else ""
    visited = " ✅" if r.get("visited") else ""
    visited_date_str = f" ({r['visited_date']})" if r.get("visited") and r.get("visited_date") else ""
    
    # State management for Edit Mode inside this fragment
    edit_key = f"edit_mode_{uid}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    # HEADER EXPANDER
    label = f"{r['name']}{icon}{fav}{visited}{visited_date_str} • {r['cuisine']} • {r['price']}"
    with st.expander(label, expanded=st.session_state[edit_key]):
        
        # --- VIEW MODE ---
        if not st.session_state[edit_key]:
            b1, b2, b3, b4 = st.columns(4)
            
            if b1.button("❤️ Favorite" if not r.get("favorite") else "💔 Unfavorite", key=f"btn_fav_{uid}", use_container_width=True):
                r["favorite"] = not r.get("favorite")
                update_place_in_db(r)
                st.rerun() # Rerun fragment only
                
            if b2.button("✅ Visited" if not r.get("visited") else "❌ Unvisited", key=f"btn_vis_{uid}", use_container_width=True):
                r["visited"] = not r.get("visited")
                if r["visited"] and not r.get("visited_date"):
                    r["visited_date"] = date.today().strftime("%B %d, %Y")
                update_place_in_db(r)
                st.rerun()

            if b3.button("Edit ✏️", key=f"btn_edit_{uid}", use_container_width=True):
                st.session_state[edit_key] = True
                st.rerun()

            if b4.button("Delete 🗑️", key=f"btn_del_{uid}", type="primary", use_container_width=True):
                delete_images_from_storage(r.get("images", []))
                supabase.table("restaurants").delete().eq("id", uid).execute()
                st.session_state.restaurants = [x for x in st.session_state.restaurants if x['id'] != uid]
                # We need to rerun the whole app to remove the card from the list
                st.query_params["reload"] = "true" 
                # (Fragments cannot delete themselves from the parent list easily without parent rerun)

            st.markdown(f"**📍 {r.get('location')}**")
            st.markdown(f"[{r.get('address')}]({google_maps_link(r.get('address'), r['name'])})")
            
            if r.get("images"):
                st.markdown("---")
                cols = st.columns(3)
                for i, img in enumerate(r["images"]):
                    cols[i % 3].image(img, use_container_width=True)

            if r.get("reviews"):
                st.markdown("---")
                st.markdown("**📝 Notes**")
                for rev in reversed(r["reviews"]):
                    st.caption(f"{rev['date']}")
                    st.write(f"{rev['comment']}")
                    st.divider()

        # --- EDIT MODE ---
        else:
            with st.form(key=f"form_edit_{uid}"):
                st.subheader(f"Editing {r['name']}")
                new_name = st.text_input("Name", r["name"])
                c1, c2 = st.columns(2)
                new_cuisine = c1.selectbox("Cuisine", CUISINES, index=CUISINES.index(r["cuisine"]) if r["cuisine"] in CUISINES else 0)
                new_price = c2.selectbox("Price", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
                
                c3, c4 = st.columns(2)
                new_loc = c3.selectbox("Neighborhood", NEIGHBORHOODS, index=NEIGHBORHOODS.index(r["location"]) if r["location"] in NEIGHBORHOODS else 0)
                new_type = c4.selectbox("Type", ["restaurant", "cocktail_bar"], index=0 if r["type"] == "restaurant" else 1)
                
                new_addr = st.text_input("Address", r["address"])
                
                # Visit Date Logic
                new_visited = st.checkbox("Visited?", value=r.get("visited", False))
                new_date_val = None
                if new_visited:
                    current_date = parse_date_str(r.get("visited_date"))
                    new_date_val = st.date_input("Date Visited", value=current_date)
                
                # Image Management
                current_imgs = r.get("images", [])
                imgs_to_keep = []
                st.write("**Manage Photos**")
                if current_imgs:
                    cols = st.columns(3)
                    for i, img in enumerate(current_imgs):
                        with cols[i%3]:
                            st.image(img, width=100)
                            if not st.checkbox("Delete", key=f"del_img_{uid}_{i}"):
                                imgs_to_keep.append(img)
                
                new_uploads = st.file_uploader("Add Photos", type=["jpg","png","webp"], accept_multiple_files=True)
                
                # Review Management
                st.write("**Add Note**")
                new_note = st.text_area("New Note")

                submitted = st.form_submit_button("Save Changes", type="primary")
                
                if submitted:
                    # Handle Image Deletions from Storage
                    imgs_to_delete = [url for url in current_imgs if url not in imgs_to_keep]
                    if imgs_to_delete:
                        delete_images_from_storage(imgs_to_delete)
                    
                    # Handle New Uploads
                    if new_uploads:
                        new_urls = upload_images_to_supabase(new_uploads, new_name)
                        imgs_to_keep.extend(new_urls)
                    
                    # Update Data Object
                    r["name"] = new_name
                    r["cuisine"] = new_cuisine
                    r["price"] = new_price
                    r["location"] = new_loc
                    r["address"] = new_addr
                    r["type"] = new_type
                    r["visited"] = new_visited
                    r["visited_date"] = new_date_val.strftime("%B %d, %Y") if new_visited and new_date_val else None
                    r["images"] = imgs_to_keep
                    
                    if new_note.strip():
                        r["reviews"].append({
                            "comment": new_note.strip(),
                            "reviewer": "You",
                            "date": datetime.now().strftime("%B %d, %Y")
                        })
                    
                    update_place_in_db(r)
                    st.session_state[edit_key] = False # Exit edit mode
                    st.success("Updated!")
                    st.rerun()

# ==================== MAIN PAGE LOGIC ====================

# Check for forced reload (from delete action)
if st.query_params.get("reload"):
    st.query_params.clear()
    st.rerun()

# --- VIEW ALL PLACES ---
if action == "View All Places":
    st.header("All Places 👀")
    
    col_search, col_sort = st.columns([5, 3])
    search = col_search.text_input("🔍 Search", placeholder="Name, cuisine, or location...")
    sort_by = col_sort.selectbox("Sort", ["A-Z", "Favorites First", "Recently Visited"])

    # Filtering
    filtered = restaurants
    if search:
        s = search.lower()
        filtered = [r for r in restaurants if s in r["name"].lower() or s in r["cuisine"].lower() or s in r["location"].lower()]

    # Sorting
    if sort_by == "Favorites First":
        filtered.sort(key=lambda x: (not x.get("favorite", False), x["name"]))
    elif sort_by == "Recently Visited":
        # Sort by visited date (parsing text to date), putting None last
        def get_date(r):
            if not r.get("visited") or not r.get("visited_date"): return date.min
            return parse_date_str(r["visited_date"])
        filtered.sort(key=get_date, reverse=True)
    else:
        filtered.sort(key=lambda x: x["name"])

    st.caption(f"Showing {len(filtered)} places")

    # Render List
    for idx, r in enumerate(filtered):
        render_place_card(r, idx)


# --- ADD A PLACE ---
elif action == "Add a Place":
    st.header("Add a New Place 📍")
    
    with st.container(border=True):
        name = st.text_input("Name*")
        c1, c2 = st.columns(2)
        cuisine = c1.selectbox("Cuisine*", CUISINES)
        price = c2.selectbox("Price*", ["$", "$$", "$$$", "$$$$"])
        
        c3, c4 = st.columns(2)
        location = c3.selectbox("Neighborhood*", NEIGHBORHOODS)
        p_type = c4.selectbox("Type*", ["restaurant", "cocktail_bar"], format_func=lambda x: "Restaurant 🍽️" if x=="restaurant" else "Bar 🍸")
        
        address = st.text_input("Address*")
        
        # Interactive Visited Check
        is_visited = st.checkbox("I've visited this place")
        visited_d = None
        if is_visited:
            visited_d = st.date_input("Date Visited", value=date.today())
            
        uploaded = st.file_uploader("Photos", accept_multiple_files=True, type=["png","jpg","jpeg","webp"])
        notes = st.text_area("Initial Notes")

        if st.button("Save Place", type="primary", use_container_width=True):
            if not name or not address:
                st.error("Name and Address are required.")
            else:
                with st.spinner("Saving..."):
                    img_urls = []
                    if uploaded:
                        img_urls = upload_images_to_supabase(uploaded, name)
                    
                    new_place = {
                        "name": name.strip(),
                        "cuisine": cuisine,
                        "price": price,
                        "location": location,
                        "address": address,
                        "type": p_type,
                        "favorite": False,
                        "visited": is_visited,
                        "visited_date": visited_d.strftime("%B %d, %Y") if is_visited else None,
                        "reviews": [{"comment": notes, "reviewer": "You", "date": datetime.now().strftime("%B %d, %Y")}] if notes else [],
                        "images": img_urls
                    }
                    
                    try:
                        res = supabase.table("restaurants").insert(new_place).execute()
                        # Update local cache
                        if res.data:
                            st.session_state.restaurants.append(res.data[0])
                        st.success(f"Added {name}!")
                        # Clear form by rerunning
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving: {e}")

# --- RANDOM PICK ---
else:
    st.header("Random Picker 🎲")
    
    if not restaurants:
        st.info("Add some places first!")
    else:
        # Filters
        with st.expander("🕵️ Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            f_cuisine = c1.multiselect("Cuisine", sorted(list(set(r["cuisine"] for r in restaurants))))
            f_loc = c2.multiselect("Neighborhood", sorted(list(set(r["location"] for r in restaurants))))
            f_price = c3.multiselect("Price", ["$", "$$", "$$$", "$$$$"])
            
            c4, c5 = st.columns(2)
            f_fav = c4.checkbox("❤️ Favorites Only")
            f_visit = c5.radio("Status", ["All", "Visited Only", "New Places Only"], horizontal=True)

        # Filter Logic
        pool = restaurants
        if f_cuisine: pool = [r for r in pool if r["cuisine"] in f_cuisine]
        if f_loc: pool = [r for r in pool if r["location"] in f_loc]
        if f_price: pool = [r for r in pool if r["price"] in f_price]
        if f_fav: pool = [r for r in pool if r.get("favorite")]
        if f_visit == "Visited Only": pool = [r for r in pool if r.get("visited")]
        if f_visit == "New Places Only": pool = [r for r in pool if not r.get("visited")]

        st.markdown(f"**Pool Size:** {len(pool)} places")
        
        if st.button("🎲 ROLL THE DICE", type="primary", use_container_width=True):
            if pool:
                st.session_state.last_pick = random.choice(pool)
            else:
                st.warning("No places match these filters.")

        # Display Result
        if "last_pick" in st.session_state and st.session_state.last_pick:
            st.divider()
            # We reuse the same fragment function for consistency!
            st.subheader("🎉 The Winner Is:")
            render_place_card(st.session_state.last_pick, 9999)
