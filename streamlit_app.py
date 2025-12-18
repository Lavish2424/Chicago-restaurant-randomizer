import streamlit as st
import json
import os
import random
from datetime import datetime

DATA_FILE = "restaurants.json"
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

CUISINES = [
    "Chinese",
    "Italian",
    "American",
    "Mexican",
    "Japanese",
    "Indian",
    "Thai",
    "French",
    "Korean",
    "Seafood",
    "Steakhouse",
    "Cocktails",
    "Other"
]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            st.error("Data file is corrupted. Starting with empty list.")
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

st.title("🍽️ Chicago Restaurant/Bar Randomizer")
st.markdown("Add, edit, delete, review, and randomly pick Chicago eats & drinks!")

st.sidebar.header("Actions")
action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Places",
     "Add a Place",
     "Add a Review",
     "Random Pick (with filters)"]
)

def delete_restaurant(index):
    r = restaurants[index]
    if r.get("photos"):
        for photo_path in r["photos"]:
            if os.path.exists(photo_path):
                os.remove(photo_path)
    del restaurants[index]
    save_data(restaurants)
    st.success(f"{r['name']} deleted successfully.")
    st.rerun()

def save_edited_restaurant(index, updated_data, new_photos, photos_to_delete):
    r = restaurants[index]
    for photo_path in photos_to_delete:
        if os.path.exists(photo_path):
            os.remove(photo_path)
        if photo_path in r["photos"]:
            r["photos"].remove(photo_path)

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

    r.update(updated_data)
    r["photos"].extend(added_paths)
    save_data(restaurants)
    st.success(f"{updated_data['name']} updated successfully!")
    st.rerun()

if action == "Add a Place":
    st.header("Add New Place")
    with st.form("add_place"):
        name = st.text_input("Name*", placeholder="e.g., Lou Malnati's")
        
        cuisine_option = st.selectbox("Cuisine/Style*", options=CUISINES)
        if cuisine_option == "Other":
            cuisine = st.text_input("Enter custom cuisine*", placeholder="e.g., Vietnamese, Mediterranean")
        else:
            cuisine = cuisine_option
        
        price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"])

        location_option = st.selectbox(
            "Neighborhood*",
            options=NEIGHBORHOODS + ["Other"]
        )
        if location_option == "Other":
            location = st.text_input("Custom neighborhood*", placeholder="e.g., Logan Square")
        else:
            location = location_option

        address = st.text_input("Address*", placeholder="e.g., 123 N Wacker Dr, Chicago, IL")

        place_type = st.selectbox(
            "Type*",
            options=["restaurant", "cocktail_bar"],
            format_func=lambda x: "Restaurant 🍽️" if x == "restaurant" else "Cocktail Bar 🍸",
            index=0
        )

        uploaded_photos = st.file_uploader(
            "Upload Photos (optional)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True
        )

        submitted = st.form_submit_button("Add Place")
        if submitted:
            required_fields = [name, cuisine, location, address]
            if not all(required_fields):
                st.error("Please fill in all required fields (*)")
            elif any(r["name"].lower() == name.lower() for r in restaurants):
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

                restaurants.append({
                    "name": name.strip(),
                    "cuisine": cuisine.strip(),
                    "price": price,
                    "location": location.strip(),
                    "address": address.strip(),
                    "type": place_type,
                    "photos": photo_paths,
                    "reviews": []
                })
                save_data(restaurants)
                st.success(f"{name} added successfully!")
                st.rerun()

elif action == "Add a Review":
    st.header("Leave a Review")
    if not restaurants:
        st.info("No places yet — add one first!")
    else:
        names = [r["name"] for r in restaurants]
        selected = st.selectbox("Choose place to review", names)
        with st.form("add_review"):
            rating = st.slider("Rating (stars)", 1, 5, 4)
            comment = st.text_area("Your thoughts*", placeholder="What did you like? Any standout dishes or drinks?")
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

elif action == "View All Places":
    st.header("All Places")
    if not restaurants:
        st.info("No places added yet.")
    else:
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
            st.write(f"**Found {len(filtered_restaurants)} place(s)** matching '{search_term}'")

        for idx, r in enumerate(sorted(filtered_restaurants, key=lambda x: x["name"].lower())):
            type_icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
            review_text = ""
            if r["reviews"]:
                avg = sum(rev["rating"] for rev in r["reviews"]) / len(r["reviews"])
                review_text = f" • {avg:.1f}⭐ ({len(r['reviews'])})"

            with st.expander(f"{r['name']}{type_icon} • {r['cuisine']} • {r['price']} • {r['location']}{review_text}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Address:** {r.get('address', 'Not provided')}")
                with col2:
                    if st.button("Edit ✏️", key=f"edit_{idx}"):
                        st.session_state.editing_index = idx
                        st.rerun()

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

                if r.get("photos"):
                    st.write("**Photos:**")
                    cols = st.columns(3)
                    for p_idx, photo_path in enumerate(r["photos"]):
                        if os.path.exists(photo_path):
                            cols[p_idx % 3].image(photo_path, use_column_width=True)

                if r["reviews"]:
                    st.write("**Reviews:**")
                    for rev in reversed(r["reviews"]):
                        st.write(f"**{rev['rating']}⭐** — {rev['reviewer']} ({rev['date']})")
                        st.write(f"{rev['comment']}")
                        st.markdown("---")
                else:
                    st.write("_No reviews yet — be the first!_")

        if "editing_index" in st.session_state:
            edit_idx = st.session_state.editing_index
            r = restaurants[edit_idx]
            st.markdown("---")
            st.subheader(f"Editing: {r['name']}")

            with st.form("edit_restaurant"):
                new_name = st.text_input("Name*", value=r["name"])
                
                current_cuisine = r["cuisine"]
                cuisine_option = st.selectbox(
                    "Cuisine/Style*",
                    options=CUISINES,
                    index=CUISINES.index(current_cuisine) if current_cuisine in CUISINES else CUISINES.index("Other")
                )
                if cuisine_option == "Other":
                    new_cuisine = st.text_input("Custom cuisine*", value=current_cuisine if current_cuisine not in CUISINES else "")
                else:
                    new_cuisine = cuisine_option
                
                new_price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"], index=["$", "$$", "$$$", "$$$$"].index(r["price"]))

                current_location = r["location"]
                location_option = st.selectbox("Neighborhood*", options=NEIGHBORHOODS + ["Other"], index=NEIGHBORHOODS.index(current_location) if current_location in NEIGHBORHOODS else len(NEIGHBORHOODS))
                if location_option == "Other":
                    new_location = st.text_input("Custom neighborhood*", value=current_location)
                else:
                    new_location = location_option

                new_address = st.text_input("Address*", value=r.get("address", ""))

                new_type = st.selectbox(
                    "Type*",
                    options=["restaurant", "cocktail_bar"],
                    format_func=lambda x: "Restaurant 🍽️" if x == "restaurant" else "Cocktail Bar 🍸",
                    index=0 if r.get("type", "restaurant") == "restaurant" else 1
                )

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
                        st.warning("Another place with this name already exists!")
                    else:
                        updated_data = {
                            "name": new_name.strip(),
                            "cuisine": new_cuisine.strip(),
                            "price": new_price,
                            "location": new_location.strip(),
                            "address": new_address.strip(),
                            "type": new_type,
                        }
                        save_edited_restaurant(edit_idx, updated_data, new_photos, photos_to_delete)

else:  # Random Pick
    st.header("🎲 Random Place Picker")
    st.markdown("Apply filters below, then let fate decide!")
    if not restaurants:
        st.info("No places yet — add some first!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            all_cuisines = sorted({r["cuisine"] for r in restaurants})
            cuisine_filter = st.multiselect("Cuisine", options=all_cuisines, default=[])
            
            all_prices = sorted({r["price"] for r in restaurants}, key=lambda x: len(x))
            price_filter = st.multiselect("Price Range", options=all_prices, default=[])
            
            type_filter = st.selectbox(
                "Type",
                options=["all", "restaurant", "cocktail_bar"],
                format_func=lambda x: {
                    "all": "All Places",
                    "restaurant": "Only Restaurants 🍽️",
                    "cocktail_bar": "Only Cocktail Bars 🍸"
                }[x],
                index=0
            )
            
        with col2:
            all_locations = sorted({r["location"] for r in restaurants})
            location_filter = st.multiselect("Neighborhood", options=all_locations, default=[])

        filtered = restaurants.copy()
        
        if type_filter == "restaurant":
            filtered = [r for r in filtered if r.get("type", "restaurant") == "restaurant"]
        elif type_filter == "cocktail_bar":
            filtered = [r for r in filtered if r.get("type") == "cocktail_bar"]
        
        if cuisine_filter:
            filtered = [r for r in filtered if r["cuisine"] in cuisine_filter]
        if price_filter:
            filtered = [r for r in filtered if r["price"] in price_filter]
        if location_filter:
            filtered = [r for r in filtered if r["location"] in location_filter]

        st.write(f"**{len(filtered)} place(s)** match your filters.")
        
        if len(filtered) == 0:
            st.warning("No places match your current filters. Try broadening them!")
        else:
            if st.button("🎲 Pick Random Place!", type="primary", use_container_width=True, key="pick_button"):
                choice = random.choice(filtered)
                st.session_state.last_random_choice = choice
                st.balloons()
                st.rerun()
                
            if "last_random_choice" in st.session_state:
                choice = st.session_state.last_random_choice
                # Only show if it still matches current filters
                if choice in filtered:
                    type_tag = " 🍸 Cocktail Bar" if choice.get("type") == "cocktail_bar" else " 🍽️ Restaurant"
                    st.markdown(f"## Your pick: **{choice['name']}**{type_tag}")
                    st.write(f"**Cuisine:** {choice['cuisine']} • **Price:** {choice['price']} • **Location:** {choice['location']}")
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
                        
                    if st.button("🎲 Pick Again!", type="secondary", use_container_width=True, key="again_button"):
                        choice = random.choice(filtered)
                        st.session_state.last_random_choice = choice
                        st.rerun()
                else:
                    st.info("Your previous pick no longer matches the filters — pick a new one!")
                    if "last_random_choice" in st.session_state:
                        del st.session_state.last_random_choice

st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")
