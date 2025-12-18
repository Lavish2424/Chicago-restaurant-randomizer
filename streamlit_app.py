import streamlit as st
import json
import os
import random
from datetime import datetime

DATA_FILE = "restaurants.json"
IMAGES_DIR = "images"

# Create images directory if it doesn't exist
os.makedirs(IMAGES_DIR, exist_ok=True)

# Predefined neighborhoods
NEIGHBORHOODS = [
    "Fulton Market",
    "River North",
    "Gold Coast",
    "South Loop",
    "Chinatown",
    "Pilsen",
    "West Town"
]

# Load data
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.error("Data file is corrupted. Starting with empty list.")
            return []
    return []

# Save data
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Initialize data in session state
if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

st.title("🍽️ Chicago Restaurant Randomizer")
st.markdown("Add, edit, delete, review, and randomly pick Chicago eats!")

# Sidebar for actions
st.sidebar.header("Actions")
action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Restaurants",
     "Add a Restaurant",
     "Add a Review",
     "Random Pick (with filters)"]
)

# Helper to delete restaurant and its photos
def delete_restaurant(index):
    r = restaurants[index]
    # Delete photos from disk
    if r.get("photos"):
        for photo_path in r["photos"]:
            if os.path.exists(photo_path):
                os.remove(photo_path)
    # Remove from list
    del restaurants[index]
    save_data(restaurants)
    st.success(f"{r['name']} deleted successfully.")
    st.rerun()

# Helper to save edited restaurant
def save_edited_restaurant(index, updated_data, new_photos, photos_to_delete):
    r = restaurants[index]
   
    # Delete selected photos
    for photo_path in photos_to_delete:
        if os.path.exists(photo_path):
            os.remove(photo_path)
        if photo_path in r["photos"]:
            r["photos"].remove(photo_path)
   
    # Add new photos
    added_paths = []
    if new_photos:
        safe_name = "".join(c for c in updated_data["name"] if c.isalnum() or c in " -_").replace(" ", "_")
        for photo in new_photos:
            filename = f"{safe_name}_{photo.name}"
            filepath = os.path.join(IMAGES_DIR, filename)
            counter = 1
            while os.path.exists(filepath):
                filename = f"{safe_name}_{counter}_{photo.name}"
                filepath = os.path.join(IMAGES_DIR, filename)
                counter += 1
            with open(filepath, "wb") as f:
                f.write(photo.getbuffer())
            added_paths.append(filepath)
   
    # Update fields
    r.update(updated_data)
    r["photos"].extend(added_paths)
   
    save_data(restaurants)
    st.success(f"{updated_data['name']} updated successfully!")
    st.rerun()

if action == "Add a Restaurant":
    st.header("Add New Restaurant")
    with st.form("add_restaurant"):
        name = st.text_input("Restaurant Name*", placeholder="e.g., Lou Malnati's")
        cuisine = st.text_input("Cuisine*", placeholder="e.g., Italian, Deep Dish Pizza")
        price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"])
       
        location_option = st.selectbox(
            "Neighborhood/Location in Chicago*",
            options=NEIGHBORHOODS + ["Other"]
        )
        if location_option == "Other":
            location = st.text_input("Enter custom neighborhood*", placeholder="e.g., Logan Square")
        else:
            location = location_option
       
        address = st.text_input("Address*", placeholder="e.g., 123 N Wacker Dr, Chicago, IL")
        
        
        uploaded_photos = st.file_uploader(
            "Upload Photos (optional, multiple allowed)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True
        )
        submitted = st.form_submit_button("Add Restaurant")
        if submitted:
            if not all([name, cuisine, location, address]):
                st.error("Please fill in all required fields (*)")
            elif any(r["name"].lower() == name.lower() for r in restaurants):
                st.warning("This restaurant already exists!")
            else:
                photo_paths = []
                if uploaded_photos:
                    safe_name = "".join(c for c in name if c.isalnum() or c in " -_").replace(" ", "_")
                    for photo in uploaded_photos:
                        filename = f"{safe_name}_{photo.name}"
                        filepath = os.path.join(IMAGES_DIR, filename)
                        counter = 1
                        while os.path.exists(filepath):
                            filename = f"{safe_name}_{counter}_{photo.name}"
                            filepath = os.path.join(IMAGES_DIR, filename)
                            counter += 1
                        with open(filepath, "wb") as f:
                            f.write(photo.getbuffer())
                        photo_paths.append(filepath)
                restaurants.append({
                    "name": name.strip(),
                    "cuisine": cuisine.strip(),
                    "price": price,
                    "location": location.strip(),
                    "address": address.strip(),
                    "visited": visited,
                    "photos": photo_paths,
                    "reviews": []
                })
                save_data(restaurants)
                st.success(f"{name} added successfully!")
                st.rerun()

elif action == "Add a Review":
    st.header("Leave a Review")
    if not restaurants:
        st.info("No restaurants yet — add one first!")
    else:
        names = [r["name"] for r in restaurants]
        selected = st.selectbox("Choose restaurant to review", names)
        with st.form("add_review"):
            rating = st.slider("Rating (stars)", 1, 5, 4)
            comment = st.text_area("Your thoughts*", placeholder="What did you like? Any standout dishes?")
            reviewer = st.text_input("Your name (optional)", placeholder="e.g., Alex")
            submitted = st.form_submit_button("Submit Review")
            if submitted:
                if not comment.strip():
                    st.error("Please write a comment!")
                else:
                    review = {
                        "rating": rating,
                        "comment": comment.strip(),
                        "reviewer": reviewer.strip() or "Anonymous",
                        "date": datetime.now().strftime("%B %d, %Y")
                    }
                    for r in restaurants:
                        if r["name"] == selected:
                            r["reviews"].append(review)
                            break
                    save_data(restaurants)
                    st.success("Thank you! Review added 🎉")
                    st.rerun()

elif action == "View All Restaurants":
    st.header("All Restaurants")
    
    if not restaurants:
        st.info("No restaurants added yet.")
    else:
        # Search bar
        search_term = st.text_input("🔍 Search by name, cuisine, or neighborhood")
        
        filtered_restaurants = restaurants
        if search_term:
            search_lower = search_term.lower()
            filtered_restaurants = [
                r for r in restaurants
                if search_lower in r["name"].lower()
                or search_lower in r["cuisine"].lower()
                or search_lower in r["location"].lower()
            ]
            st.write(f"**Found {len(filtered_restaurants)} restaurant(s)** matching '{search_term}'")
        
        for idx, r in enumerate(sorted(filtered_restaurants, key=lambda x: x["name"].lower())):
            # Rating and visited badge
            review_text = ""
            if r["reviews"]:
                avg = sum(rev["rating"] for rev in r["reviews"]) / len(r["reviews"])
                review_text = f" • {avg:.1f}⭐ ({len(r['reviews'])})"
            
            visited_badge = " ✅ Visited" if r.get("visited", False) else ""
            
            with st.expander(f"{r['name']}{visited_badge} • {r['cuisine']} • {r['price']} • {r['location']}{review_text}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Address:** {r.get('address', 'Not provided')}")
                with col2:
                    if st.button("Edit ✏️", key=f"edit_{idx}"):
                        st.session_state.editing_index = idx
                        st.rerun()
                    
                    # Improved delete confirmation
                    delete_key = f"delete_confirm_{idx}"
                    if delete_key in st.session_state:
                        col_del, col_cancel = st.columns(2)
                        with col_del:
                            if st.button("🗑️ Confirm Delete", key=f"confirm_{idx}", type="primary"):
                                delete_restaurant(idx)
                        with col_cancel:
                            if st.button("Cancel", key=f"cancel_{idx}"):
                                del st.session_state[delete_key]
                                st.rerun()
                    else:
                        if st.button("Delete 🗑️", key=f"delete_{idx}", type="secondary"):
                            st.session_state[delete_key] = True
                            st.rerun()
                
                # Show current photos
                if r.get("photos"):
                    st.write("**Photos:**")
                    cols = st.columns(3)
                    for p_idx, photo_path in enumerate(r["photos"]):
                        if os.path.exists(photo_path):
                            cols[p_idx % 3].image(photo_path, use_column_width=True)
                
                # Reviews
                if r["reviews"]:
                    st.write("**Reviews:**")
                    for rev in reversed(r["reviews"]):
                        st.write(f"**{rev['rating']}⭐** — {rev['reviewer']} ({rev['date']})")
                        st.write(f"{rev['comment']}")
                        st.markdown("---")
                else:
                    st.write("_No reviews yet — be the first!_")
        
        # Edit form
        if "editing_index" in st.session_state:
            edit_idx = st.session_state.editing_index
            r = restaurants[edit_idx]
           
            st.markdown("---")
            st.subheader(f"Editing: {r['name']}")
           
            with st.form("edit_restaurant"):
                new_name = st.text_input("Restaurant Name*", value=r["name"])
                new_cuisine = st.text_input("Cuisine*", value=r["cuisine"])
                new_price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))
               
                current_location = r["location"]
                if current_location in NEIGHBORHOODS:
                    location_option = st.selectbox("Neighborhood*", options=NEIGHBORHOODS + ["Other"], index=NEIGHBORHOODS.index(current_location))
                else:
                    location_option = st.selectbox("Neighborhood*", options=NEIGHBORHOODS + ["Other"], index=len(NEIGHBORHOODS))
                if location_option == "Other":
                    new_location = st.text_input("Custom neighborhood*", value=current_location)
                else:
                    new_location = location_option
               
                new_address = st.text_input("Address*", value=r.get("address", ""))
                
                new_visited = st.checkbox("Already visited? ✅", value=r.get("visited", False))
               
                st.write("**Current Photos (check to delete):**")
                photos_to_delete = []
                if r.get("photos"):
                    cols = st.columns(3)
                    for p_idx, photo_path in enumerate(r["photos"]):
                        if os.path.exists(photo_path):
                            with cols[p_idx % 3]:
                                st.image(photo_path, use_column_width=True)
                                if st.checkbox("Delete this photo", key=f"del_photo_{edit_idx}_{p_idx}"):
                                    photos_to_delete.append(photo_path)
               
                new_photos = st.file_uploader(
                    "Add more photos (optional)",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=True,
                    key=f"new_photos_{edit_idx}"
                )
               
                col_save, col_cancel = st.columns(2)
                with col_save:
                    save_submitted = st.form_submit_button("Save Changes")
                with col_cancel:
                    cancel = st.form_submit_button("Cancel")
               
                if cancel:
                    del st.session_state.editing_index
                    st.rerun()
               
                if save_submitted:
                    if not all([new_name, new_cuisine, new_location, new_address]):
                        st.error("All required fields must be filled.")
                    elif new_name.lower() != r["name"].lower() and any(existing["name"].lower() == new_name.lower() for existing in restaurants if existing != r):
                        st.warning("Another restaurant with this name already exists!")
                    else:
                        updated_data = {
                            "name": new_name.strip(),
                            "cuisine": new_cuisine.strip(),
                            "price": new_price,
                            "location": new_location.strip(),
                            "address": new_address.strip(),
                            "visited": new_visited,
                        }
                        save_edited_restaurant(edit_idx, updated_data, new_photos, photos_to_delete)

else:  # Random Pick
    st.header("🎲 Random Restaurant Picker")
    st.markdown("Apply filters below, then let fate decide!")

    if not restaurants:
        st.info("No restaurants yet — add some first!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            all_cuisines = sorted({r["cuisine"] for r in restaurants if r["cuisine"]})
            cuisine_filter = st.multiselect("Cuisine", options=all_cuisines, default=[])
            all_prices = sorted({r["price"] for r in restaurants}, key=lambda x: len(x))
            price_filter = st.multiselect("Price Range", options=all_prices, default=[])
        with col2:
            all_locations = sorted({r["location"] for r in restaurants if r["location"]})
            location_filter = st.multiselect("Neighborhood", options=all_locations, default=[])

        filtered = restaurants.copy()
        if cuisine_filter:
            filtered = [r for r in filtered if r["cuisine"] in cuisine_filter]
        if price_filter:
            filtered = [r for r in filtered if r["price"] in price_filter]
        if location_filter:
            filtered = [r for r in filtered if r["location"] in location_filter]
        if exclude_visited:
            filtered = [r for r in filtered if not r.get("visited", False)]

        st.write(f"**{len(filtered)} restaurant(s)** match your filters.")

        if filtered:
            # New random pick
            if st.button("🎲 Pick Random Restaurant!", type="primary", use_container_width=True, key="new_pick"):
                choice = random.choice(filtered)
                st.session_state.last_random_choice = choice
                st.balloons()
                st.rerun()

            # Show current/last choice with "Pick Again"
            if "last_random_choice" in st.session_state and st.session_state.last_random_choice in filtered:
                choice = st.session_state.last_random_choice
                st.markdown(f"## 🍴 Your pick: **{choice['name']}**")
                visited_tag = " ✅ (Already visited)" if choice.get("visited", False) else ""
                st.write(f"**Cuisine:** {choice['cuisine']} • **Price:** {choice['price']} • **Location:** {choice['location']}{visited_tag}")
                st.write(f"**Address:** {choice.get('address', 'Not provided')}")

                if choice.get("photos"):
                    st.markdown("### Photos")
                    cols = st.columns(3)
                    for idx, photo_path in enumerate(choice["photos"]):
                        if os.path.exists(photo_path):
                            cols[idx % 3].image(photo_path, use_column_width=True)

                if choice["reviews"]:
                    st.markdown("### Recent Reviews")
                    for rev in choice["reviews"][-3:]:
                        st.write(f"**{rev['rating']}⭐** — {rev['reviewer']} ({rev['date']})")
                        st.write(f"_{rev['comment']}_")
                else:
                    st.info("No reviews yet — you'll be the pioneer!")

                if st.button("🎲 Pick Again!", type="secondary", use_container_width=True):
                    choice = random.choice(filtered)
                    st.session_state.last_random_choice = choice
                    st.rerun()

            elif "last_random_choice" in st.session_state:
                # Previous choice no longer matches filters
                del st.session_state.last_random_choice
                st.info("Previous pick no longer matches current filters — pick again!")
        else:
            st.warning("No restaurants match your filters — try broadening them!")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")
