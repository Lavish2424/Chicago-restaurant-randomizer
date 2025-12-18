import streamlit as st
import json
import os
import random
import urllib.parse
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
    "Pizza",
    "Burgers",
    "Seafood",
    "Steakhouse",
    "Bar Food",
    "Cocktails",
    "Other"
]

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for place in data:
                    if "favorite" not in place:
                        place["favorite"] = False
                    for review in place.get("reviews", []):
                        if "date" not in review:
                            review["date"] = "Unknown date"
                return data
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
st.markdown("Add, edit, delete, review, favorite, and randomly pick Chicago eats & drinks!")

# Sidebar: Your name for editing reviews
st.sidebar.header("Your Info")
current_reviewer = st.sidebar.text_input("Your name (for editing your reviews)", value=st.session_state.get("current_reviewer", ""), key="reviewer_input")
if current_reviewer:
    st.session_state.current_reviewer = current_reviewer

st.sidebar.header("Actions")
action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Places",
     "Favorites ❤️",
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

def toggle_favorite(idx):
    restaurants[idx]["favorite"] = not restaurants[idx].get("favorite", False)
    save_data(restaurants)
    st.rerun()

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    encoded = urllib.parse.quote(query)
    return f"https://www.google.com/maps/search/?api=1&query={encoded}"

# Set page header
if action == "View All Places":
    st.header("All Places")
elif action == "Favorites ❤️":
    st.header("❤️ Your Favorite Places")
elif action == "Add a Place":
    st.header("Add New Place")
elif action == "Add a Review":
    st.header("Leave a Review")
elif action == "Random Pick (with filters)":
    st.header("🎲 Random Place Picker")
    st.markdown("Apply filters below, then let fate decide!")

# Helper to display reviews with edit/delete for own reviews
def display_reviews(place, global_idx):
    if place["reviews"]:
        st.write("**Reviews:**")
        for rev_idx, rev in enumerate(reversed(place["reviews"])):
            is_mine = current_reviewer and current_reviewer.strip().lower() == rev["reviewer"].strip().lower()
            stars = "★" * rev["rating"] + "☆" * (5 - rev["rating"])
            with st.container():
                col_text, col_action = st.columns([4, 1])
                with col_text:
                    st.write(f"**{stars}** — {rev['reviewer']} ({rev['date']})")
                    st.write(f"{rev['comment']}")
                with col_action:
                    if is_mine:
                        if st.button("Edit ✏️", key=f"edit_rev_{global_idx}_{rev_idx}"):
                            st.session_state.editing_review = (global_idx, len(place["reviews"]) - 1 - rev_idx)  # original index
                            st.rerun()
                        if st.button("Delete 🗑️", key=f"del_rev_{global_idx}_{rev_idx}"):
                            del place["reviews"][len(place["reviews"]) - 1 - rev_idx]
                            save_data(restaurants)
                            st.success("Review deleted.")
                            st.rerun()
                st.markdown("---")
    else:
        st.write("_No reviews yet — be the first!_")

    # Edit review form
    if st.session_state.get("editing_review") and st.session_state.editing_review[0] == global_idx:
        p_idx, r_idx = st.session_state.editing_review
        review_to_edit = restaurants[p_idx]["reviews"][r_idx]
        st.markdown("#### Editing your review")
        with st.form(f"edit_review_form_{p_idx}_{r_idx}"):
            new_rating = st.radio(
                "Update rating",
                options=[1, 2, 3, 4, 5],
                index=review_to_edit["rating"] - 1,
                format_func=lambda x: "★" * x + "☆" * (5 - x),
                horizontal=True,
                label_visibility="collapsed"
            )
            new_comment = st.text_area("Update comment", value=review_to_edit["comment"])
            col_save, col_cancel = st.columns(2)
            save_rev = col_save.form_submit_button("Save Changes")
            cancel_rev = col_cancel.form_submit_button("Cancel")
            if cancel_rev:
                del st.session_state.editing_review
                st.rerun()
            if save_rev:
                if not new_comment.strip():
                    st.error("Comment cannot be empty!")
                else:
                    restaurants[p_idx]["reviews"][r_idx]["rating"] = new_rating
                    restaurants[p_idx]["reviews"][r_idx]["comment"] = new_comment.strip()
                    save_data(restaurants)
                    del st.session_state.editing_review
                    st.success("Review updated!")
                    st.rerun()

# View All / Favorites
if action in ["View All Places", "Favorites ❤️"]:
    display_places = [r for r in restaurants if r.get("favorite", False)] if action == "Favorites ❤️" else restaurants
    
    if not display_places:
        if action == "Favorites ❤️":
            st.info("No favorites yet! Go to 'View All Places' and tap ❤️ on your top spots.")
        else:
            st.info("No places added yet.")
    else:
        search_term = st.text_input("🔍 Search by name, cuisine, or neighborhood")
        filtered = display_places
        if search_term:
            search_lower = search_term.lower()
            filtered = [r for r in filtered if search_lower in r["name"].lower() or search_lower in r["cuisine"].lower() or search_lower in r["location"].lower()]
            st.write(f"**Found {len(filtered)} place(s)** matching '{search_term}'")

        for idx, r in enumerate(sorted(filtered, key=lambda x: x["name"].lower())):
            global_idx = restaurants.index(r)
            type_icon = " 🍸" if r.get("type") == "cocktail_bar" else " 🍽️"
            fav_icon = " ❤️" if r.get("favorite", False) else ""
            review_text = f" • {sum(rev['rating'] for rev in r['reviews'])/len(r['reviews']):.1f}⭐ ({len(r['reviews'])})" if r["reviews"] else ""

            with st.expander(f"{r['name']}{type_icon}{fav_icon} • {r['cuisine']} • {r['price']} • {r['location']}{review_text}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Address:** {r.get('address', 'Not provided')}")
                    maps_url = google_maps_link(r.get("address", ""), r["name"])
                    st.markdown(f"[📍 Open in Google Maps]({maps_url})")
                with col2:
                    if st.button("❤️ Favorite" if not r.get("favorite", False) else "❤️ Unfavorite", key=f"fav_btn_{global_idx}"):
                        toggle_favorite(global_idx)
                    if st.button("Edit ✏️", key=f"edit_{global_idx}"):
                        st.session_state.editing_index = global_idx
                        st.rerun()

                    delete_key = f"delete_confirm_{global_idx}"
                    if delete_key in st.session_state:
                        col_del, col_cancel = st.columns(2)
                        with col_del:
                            if st.button("🗑️ Confirm Delete", key=f"confirm_{global_idx}", type="primary"):
                                delete_restaurant(global_idx)
                        with col_cancel:
                            if st.button("Cancel", key=f"cancel_{global_idx}"):
                                del st.session_state[delete_key]
                                st.rerun()
                    else:
                        if st.button("Delete 🗑️", key=f"delete_{global_idx}", type="secondary"):
                            st.session_state[delete_key] = True
                            st.rerun()

                if r.get("photos"):
                    st.write("**Photos:**")
                    cols = st.columns(3)
                    for p_idx, photo_path in enumerate(r["photos"]):
                        if os.path.exists(photo_path):
                            cols[p_idx % 3].image(photo_path, use_column_width=True)

                display_reviews(r, global_idx)

        # Edit place form
        if "editing_index" in st.session_state:
            edit_idx = st.session_state.editing_index
            r = restaurants[edit_idx]
            st.markdown("---")
            st.subheader(f"Editing: {r['name']}")
            # (edit form unchanged — same as before)

elif action == "Add a Place":
    with st.form("add_place"):
        # (same as before)

elif action == "Add a Review":
    if not restaurants:
        st.info("No places yet — add one first!")
    else:
        names = [r["name"] for r in restaurants]
        selected = st.selectbox("Choose place to review", names)
        with st.form("add_review", clear_on_submit=True):
            st.write("**Your Rating**")
            rating = st.radio(
                "Select your rating",
                options=[1, 2, 3, 4, 5],
                format_func=lambda x: "★" * x + "☆" * (5 - x),
                horizontal=True,
                label_visibility="collapsed"
            )
            comment = st.text_area("Your thoughts*", placeholder="What did you like? Any standout dishes or drinks?")
            reviewer = st.text_input("Your name*", value=current_reviewer or "", placeholder="e.g., Alex")

            submitted = st.form_submit_button("Submit Review")
            if submitted:
                if not reviewer.strip():
                    st.error("Please enter your name!")
                elif not comment.strip():
                    st.error("Please write a comment!")
                else:
                    review = {
                        "rating": rating,
                        "comment": comment.strip(),
                        "reviewer": reviewer.strip(),
                        "date": datetime.now().strftime("%B %d, %Y")
                    }
                    for r in restaurants:
                        if r["name"] == selected:
                            r["reviews"].append(review)
                            break
                    save_data(restaurants)
                    if reviewer.strip():
                        st.session_state.current_reviewer = reviewer.strip()
                    st.success("Thank you! Review added 🎉")
                    st.rerun()

else:  # Random Pick
    if not restaurants:
        st.info("No places yet — add some first!")
    else:
        # filters...
        # (same filtering logic)

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
                if choice in filtered:
                    # display choice
                    global_idx = restaurants.index(choice)
                    # ... photos, maps, favorite button
                    display_reviews(choice, global_idx)
                    # pick again button

st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan, made for us ❤️")
