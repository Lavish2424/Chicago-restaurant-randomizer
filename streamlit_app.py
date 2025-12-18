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
st.markdown("Add places, review them, and let fate decide where to eat next!")

# Sidebar for actions
st.sidebar.header("Actions")
action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Restaurants",
     "Add a Restaurant",
     "Add a Review",
     "Random Pick (with filters)"]
)

if action == "Add a Restaurant":
    st.header("Add New Restaurant")
    with st.form("add_restaurant"):
        name = st.text_input("Restaurant Name*", placeholder="e.g., Lou Malnati's")
        cuisine = st.text_input("Cuisine*", placeholder="e.g., Italian, Deep Dish Pizza")
        price = st.selectbox("Price Range*", ["$", "$$", "$$$", "$$$$"])
        
        # Neighborhood dropdown with "Other" option
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
            if not name or not cuisine or not location or not address:
                st.error("Please fill in all required fields (*)")
            elif any(r["name"].lower() == name.lower() for r in restaurants):
                st.warning("This restaurant already exists!")
            else:
                photo_paths = []
                if uploaded_photos:
                    for photo in uploaded_photos:
                        safe_name = "".join(c for c in name if c.isalnum() or c in " -_").replace(" ", "_")
                        filename = f"{safe_name}_{photo.name}"
                        filepath = os.path.join(IMAGES_DIR, filename)
                        counter = 1
                        original_filepath = filepath
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
        for r in sorted(restaurants, key=lambda x: x["name"].lower()):
            with st.expander(f"{r['name']} • {r['cuisine']} • {r['price']} • {r['location']}"):
                st.write(f"**Address:** {r.get('address', 'Not provided')}")
                if r.get("photos"):
                    st.write("**Photos:**")
                    cols = st.columns(3)
                    for idx, photo_path in enumerate(r["photos"]):
                        if os.path.exists(photo_path):
                            cols[idx % 3].image(photo_path, use_column_width=True)
                if r["reviews"]:
                    avg_rating = sum(rev["rating"] for rev in r["reviews"]) / len(r["reviews"])
                    st.write(f"**Average Rating: {avg_rating:.1f}⭐ ({len(r['reviews'])} reviews)**")
                    st.write("**Reviews:**")
                    for rev in reversed(r["reviews"]):
                        st.write(f"**{rev['rating']}⭐** — {rev['reviewer']} ({rev['date']})")
                        st.write(f"{rev['comment']}")
                        st.markdown("---")
                else:
                    st.write("_No reviews yet — be the first!_")

else:  # Random Pick with filters
    st.header("🎲 Random Restaurant Picker")
    st.markdown("Apply filters below, then hit the button for dinner destiny!")

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

        st.write(f"**{len(filtered)} restaurant(s)** match your filters.")

        if filtered:
            if st.button("🎲 Pick Random Restaurant!", type="primary", use_container_width=True):
                choice = random.choice(filtered)
                st.balloons()
                st.markdown(f"## 🍴 Your destiny: **{choice['name']}**")
# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Built by Alan made for us ❤️")
