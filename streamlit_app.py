import streamlit as st
import json
import os
from datetime import datetime

DATA_FILE = "restaurants.json"

# Load data
def load_data():
if os.path.exists(DATA_FILE):
with open(DATA_FILE, "r") as f:
return json.load(f)
return []

# Save data
def save_data(data):
with open(DATA_FILE, "w") as f:
json.dump(data, f, indent=4)

# Initialize data
if "restaurants" not in st.session_state:
st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

st.title("🍽️ Chicago Restaurant Randomizer")
st.markdown("A shared list for you and your partner — add places, review them, and let fate decide where to eat next!")

# Sidebar for actions
st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?",
["View All Restaurants",
"Add a Restaurant",
"Add a Review",
"Random Pick (with filters)"])

if action == "Add a Restaurant":
st.header("Add New Restaurant")
with st.form("add_restaurant"):
name = st.text_input("Restaurant Name")
cuisine = st.text_input("Cuisine (e.g., Italian, Tacos, Sushi)")
price = st.selectbox("Price Range", ["$", "$$", "$$$", "$$$$"])
location = st.text_input("Neighborhood/Location in Chicago")
submitted = st.form_submit_button("Add Restaurant")
if submitted and name:
if any(r["name"].lower() == name.lower() for r in restaurants):
st.warning("This restaurant already exists!")
else:
restaurants.append({
"name": name,
"cuisine": cuisine,
"price": price,
"location": location,
"reviews": []
})
save_data(restaurants)
st.success(f"{name} added!")
st.rerun()

elif action == "Add a Review":
st.header("Leave a Review")
if not restaurants:
st.info("No restaurants yet — add one first!")
else:
names = [r["name"] for r in restaurants]
selected = st.selectbox("Choose restaurant", names)
with st.form("add_review"):
rating = st.slider("Rating", 1, 5, 3)
comment = st.text_area("Your thoughts")
reviewer = st.text_input("Your name (optional)", "")
submitted = st.form_submit_button("Submit Review")
if submitted:
review = {
"rating": rating,
"comment": comment,
"reviewer": reviewer or "Anonymous",
"date": datetime.now().strftime("%Y-%m-%d")
}
for r in restaurants:
if r["name"] == selected:
r["reviews"].append(review)
break
save_data(restaurants)
st.success("Review added!")
st.rerun()

elif action == "View All Restaurants":
st.header("All Restaurants")
if not restaurants:
st.info("No restaurants added yet.")
else:
for r in restaurants:
with st.expander(f"{r['name']} • {r['cuisine']} • {r['price']} • {r['location']}"):
if r["reviews"]:
st.write("**Reviews:**")
for rev in r["reviews"]:
st.write(f"**{rev['rating']}⭐** - {rev['reviewer']} ({rev['date']})")
st.write(f"{rev['comment']}")
else:
st.write("No reviews yet.")

else: # Random Pick with filters
st.header("🎲 Random Restaurant Picker")

col1, col2 = st.columns(2)
with col1:
cuisine_filter = st.multiselect("Cuisine",
options=sorted(set(r["cuisine"] for r in restaurants if r["cuisine"])),
default=[])
price_filter = st.multiselect("Price",
options=sorted(set(r["price"] for r in restaurants)),
default=[])
with col2:
location_filter = st.multiselect("Location",
options=sorted(set(r["location"] for r in restaurants if r["location"])),
default=[])

# Apply filters
filtered = restaurants
if cuisine_filter:
filtered = [r for r in filtered if r["cuisine"] in cuisine_filter]
if price_filter:
filtered = [r for r in filtered if r["price"] in price_filter]
if location_filter:
filtered = [r for r in filtered if r["location"] in location_filter]

st.write(f"**{len(filtered)} restaurants** match your filters.")

if filtered:
if st.button("🎲 Pick Random Restaurant!", type="primary"):
choice = random.choice(filtered)
st.balloons()
st.success("Your random pick is...")
st.markdown(f"### 🍴 {choice['name']}")
st.write(f"**Cuisine:** {choice['cuisine']} | **Price:** {choice['price']} | **Location:** {choice['location']}")
if choice["reviews"]:
st.write("**Recent reviews:**")
for rev in choice["reviews"][-3:]: # last 3
st.write(f"**{rev['rating']}⭐** - {rev['reviewer']}: {rev['comment']}")
else:
st.warning("No restaurants match your filters — try loosening them!")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Built with ❤️ using Streamlit • Shared between you two")
