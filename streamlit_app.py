import streamlit as st
import json
import os
import random
from datetime import datetime

DATA_FILE = "restaurants.json"  # Keeping name for backward compatibility
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

NEIGHBORHOODS = [
    "Fulton Market",
    "River North",
    "Gold Coast",
    "South Loop",
    "Chinatown",
    "Pilsen",
    "West Town"
]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                # Backward compatibility: old entries without 'type' are Restaurants
                for entry in data:
                    if "type" not in entry:
                        entry["type"] = "Restaurant"
                return data
        except json.JSONDecodeError:
            st.error("Data file is corrupted. Starting with empty list.")
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if "places" not in st.session_state:
    st.session_state.places = load_data()

places = st.session_state.places

st.title("🍽️🍸 Chicago Eats & Drinks Randomizer")
st.markdown("Add, edit, review, and randomly pick **restaurants** or **cocktail bars** in Chicago!")

st.sidebar.header("Actions")
action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Places",
     "Add a Place",
     "Add a Review",
     "Random Pick (with filters)"]
)

def delete_place(index):
    p = places[index]
    if p.get("photos"):
        for photo_path in p["photos"]:
            if os.path.exists(photo_path):
                os.remove(photo_path)
    del places[index]
    save_data(places)
    st.success(f"{p['name']} deleted successfully.")
    st.rerun()

def save_edited_place(index, updated_data, new_photos, photos_to_delete):
    p = places[index]
    for photo_path in photos_to_delete:
        if os.path.exists(photo_path):
            os.remove(photo_path)
        if photo_path in p["photos"]:
            p["photos"].remove(photo_path)
    
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
    
    p.update(updated_data)
    p["photos"].extend(added_paths)
    save_data(places)
    st.success(f"{updated_data['name']} updated successfully!")
    st.rerun()

if action == "Add a Place":
    st.header("Add New Place")
    with st.form("add_place"):
        place_type = st.selectbox("Type*", ["Restaurant", "Cocktail Bar"])
        
        name = st.text_input("Name*", placeholder="e.g., Lou Malnati's or Nine Bar")
        
        category_label = "Cuisine*" if place_type == "Restaurant" else "Style / Vibe*"
        category = st.text_input(category_label, placeholder="e.g., Deep Dish Pizza or Speakeasy Craft Cocktails")
        
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
        
        submitted = st.form_submit_button("Add Place")
        if submitted:
            if not all([name, category, location, address]):
                st.error("Please fill in all required fields (*)")
            elif any(p["name"].lower() == name.lower() for p in places):
                st.warning("This place already exists!")
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
                
                places.append({
                    "name": name.strip(),
                    "category": category.strip(),
                    "price": price,
                    "location": location.strip(),
                    "address": address.strip(),
                    "type": place_type,
                    "photos": photo_paths,
                    "reviews": []
                })
                save_data(places)
                st.success(f"{name} added successfully!")
                st.rerun()

elif action == "Add a Review":
    st.header("Leave a Review")
    if not places:
        st.info("No places yet — add one first!")
    else:
        names = [p["name"] for p in places]
        selected = st.selectbox("Choose place to review", names)
        with st.form("add_review"):
            rating = st.slider("Rating (stars)", 1, 5, 4)
            comment = st.text_area("Your thoughts*", placeholder="What did you like?")
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
                    for p in places:
                        if p["name"] == selected:
                            p["reviews"].append(review)
                            break
                    save_data(places)
                    st.success("Thank you! Review added 🎉")
                    st.rerun()

elif action == "View All Places":
    st.header("All Places")
    if not places:
        st.info("No places added yet.")
    else:
        search_term = st.text_input("🔍 Search by name, category, or neighborhood")
        
        filtered_places = places
        if search_term:
            search_lower = search_term.lower()
            filtered_places = [
                p for p in places
                if search_lower in p["name"].lower()
                or search_lower in p["category"].lower()
                or search_lower in p["location"].lower()
            ]
            st.write(f"**Found {len(filtered_places)} place(s)** matching '{search_term}'")
        
        for idx, p in enumerate(sorted(filtered_places, key=lambda x: x["name"].lower())):
            review_text = ""
            if p["reviews"]:
                avg = sum(rev["rating"] for rev in p["reviews"]) / len(p["reviews"])
                review_text = f" • {avg:.1f}⭐ ({len(p['reviews'])})"
            
            type_badge = f" • {p['type']}"
            
            category_label = "Cuisine" if p["type"] == "Restaurant" else "Style"
            with st.expander(f"{p['name']}{type_badge} • {p['category']} • {p['price']} • {p['location']}{review_text}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Address:** {p.get('address', 'Not provided')}")
                with col2:
                    if st.button("Edit ✏️", key=f"edit_{idx}"):
                        st.session_state.editing_index = idx
                        st.rerun()
                    
                    delete_key = f"delete_confirm_{idx}"
                    if delete_key in st.session_state:
                        col_del, col_cancel = st.columns(2)
                        with col_del:
                            if st.button("🗑️ Confirm Delete", key=f"confirm_{idx}", type="primary"):
                                delete_place(idx)
                        with col_cancel:
                            if st.button("Cancel", key=f"cancel_{idx}"):
                                del st.session_state[delete_key]
                                st.rerun()
                    else:
                        if st.button("Delete 🗑️", key=f"delete_{idx}", type="secondary"):
                            st.session_state[delete_key] = True
                            st.rerun()
                
                if p.get("photos"):
                    st.write("**Photos:**")
                    cols = st.columns(3)
                    for p_idx, photo_path in enumerate(p["photos"]):
                        if os.path.exists(photo_path):
                            cols[p_idx % 3].image(photo_path, use_column_width=True)
                
                if p["reviews"]:
                    st.write("**Reviews:**")
                    for rev in reversed(p["reviews"]):
                        st.write(f"**{rev['rating']}⭐** — {rev['reviewer']} ({rev['date']})")
                        st.write(f"{rev['comment']}")
                        st.markdown("---")
                else:
                    st.write("_No reviews yet — be the first!_")
        
        if "editing_index" in st.session_state:
            edit_idx = st.session_state.editing_index
            p = places[edit_idx]
            
            st.markdown("---")
            st.subheader(f"Editing: {p['name']}")
            
            with st.form("edit_place"):
                new_type = st.selectbox("Type*", ["Restaurant", "Cocktail Bar"], index=0 if p["type"] == "Restaurant" else 1)
                
                new_name = st.text_input("Name*", value=p["name"])
                
                new_category_label = "Cuisine*" if new_type == "Restaurant" else "Style / Vibe*"
                new_category = st.text_input(new_category_label, value=p["category"])
                
                new_price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(p["price"]))
                
                current_location = p["location"]
                if current_location in NEIGHBORHOODS:
                    location_option = st.selectbox("Neighborhood*", options=NEIGHBORHOODS + ["Other"], index=NEIGHBORHOODS.index(current_location))
                else:
                    location_option = st.selectbox("Neighborhood*", options=NEIGHBORHOODS + ["Other"], index=len(NEIGHBORHOODS))
                if location_option == "Other":
                    new_location = st.text_input("Custom neighborhood*", value=current_location)
                else:
                    new_location = location_option
                
                new_address = st.text_input("Address*", value=p.get("address", ""))
                
                st.write("**Current Photos (check to delete):**")
                photos_to_delete = []
                if p.get("photos"):
                    cols = st.columns(3)
                    for p_idx, photo_path in enumerate(p["photos"]):
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
                    if not all([new_name, new_category, new_location, new_address]):
                        st.error("All required fields must be filled.")
                    elif new_name.lower() != p["name"].lower() and any(existing["name"].lower() == new_name.lower() for existing in places if existing != p):
                        st.warning("Another place with this name already exists!")
                    else:
                        updated_data = {
                            "name": new_name.strip(),
                            "category": new_category.strip(),
                            "price": new_price,
                            "location": new_location.strip(),
                            "address": new_address.strip(),
                            "type": new_type,
                        }
                        save_edited_place(edit_idx, updated_data, new_photos, photos_to_delete)

else:  # Random Pick
    st.header("🎲 Random Place Picker")
    st.markdown("Apply filters below, then let fate decide your next spot!")

    if not places:
        st.info("No places yet — add some first!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            type_filter = st.multiselect("Type", options=["Restaurant", "Cocktail Bar"], default=["Restaurant", "Cocktail Bar"])
            all_categories = sorted({p["category"] for p in places})
            category_filter = st.multiselect("Cuisine / Style", options=all_categories, default=[])
        with col2:
            all_prices = sorted({p["price"] for p in places}, key=lambda x: len(x))
            price_filter = st.multiselect("Price Range", options=all_prices, default=[])
            all_locations = sorted({p["location"] for p in places})
            location_filter = st.multiselect("Neighborhood", options=all_locations, default=[])

        filtered = [p for p in places if p["type"] in type_filter]
        if category_filter:
            filtered = [p for p in filtered if p["category"] in category_filter]
        if price_filter:
            filtered = [p for p in filtered if p["price"] in price_filter]
        if location_filter:
            filtered = [p for p in filtered if p["location"] in location_filter]

        st.write(f"**{len(filtered)} place(s)** match your filters.")

        if filtered:
            if st.button("🎲 Pick Random Place!", type="primary", use_container_width=True, key="new_pick"):
                choice = random.choice(filtered)
                st.session_state.last_random_choice = choice
                st.balloons()
                st.rerun()

            if "last_random_choice" in st.session_state and st.session_state.last_random_choice in filtered:
                choice = st.session_state.last_random_choice
                st.markdown(f"## {'🍴' if choice['type'] == 'Restaurant' else '🍸'} Your pick: **{choice['name']}**")
                category_label = "Cuisine" if choice["type"] == "Restaurant" else "Style"
                st.write(f"**{category_label}:** {choice['category']} • **Price:** {choice['price']} • **Location:** {choice['location']}")
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
                del st.session_state.last_random_choice
                st.info("Previous pick no longer matches current filters — pick again!")
        else:
            st.warning("No places match your filters — try broadening them!")

st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")
