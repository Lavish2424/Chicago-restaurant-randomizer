import streamlit as st
import random
import urllib.parse
from datetime import datetime, date
from supabase import create_client, Client
import os

# ==================== SUPABASE SETUP ====================
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)
BUCKET_NAME = "restaurant-images"

# ==================== DATA ====================
def load_data():
    response = supabase.table("restaurants").select("*").execute()
    data = response.data or []
    for r in data:
        r.setdefault("favorite", False)
        r.setdefault("visited", False)
        r.setdefault("visited_date", None)
        r.setdefault("reviews", [])
        r.setdefault("images", [])
    return data

def save_data(data):
    for r in data:
        supabase.table("restaurants").update({
            "name": r["name"],
            "cuisine": r["cuisine"],
            "price": r["price"],
            "location": r["location"],
            "address": r["address"],
            "type": r["type"],
            "favorite": r.get("favorite", False),
            "visited": r.get("visited", False),
            "visited_date": r.get("visited_date"),
            "reviews": r["reviews"],
            "images": r.get("images", [])
        }).eq("id", r["id"]).execute()

if "restaurants" not in st.session_state:
    st.session_state.restaurants = load_data()

restaurants = st.session_state.restaurants

# ==================== HELPERS ====================
def toggle_favorite_by_id(place_id):
    for r in restaurants:
        if r["id"] == place_id:
            r["favorite"] = not r.get("favorite", False)
            break
    save_data(restaurants)
    st.session_state.restaurants = load_data()
    st.rerun()

def toggle_visited_by_id(place_id):
    for r in restaurants:
        if r["id"] == place_id:
            r["visited"] = not r.get("visited", False)
            break
    save_data(restaurants)
    st.session_state.restaurants = load_data()
    st.rerun()

def google_maps_link(address, name=""):
    q = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(q)}"

# ==================== UI ====================
st.markdown("<h1 style='text-align:center'>🍽️🍸 Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)

action = st.sidebar.radio(
    "What do you want to do?",
    ["View All Places", "Add a Place", "Random Pick"]
)

# ==================== VIEW ALL ====================
if action == "View All Places":
    st.header("All Places 👀")

    search = st.text_input("Search")
    filtered = restaurants

    if search:
        s = search.lower()
        filtered = [
            r for r in restaurants
            if s in r["name"].lower()
            or s in r["cuisine"].lower()
            or s in r["location"].lower()
            or s in r.get("address", "").lower()
        ]

    filtered = sorted(filtered, key=lambda x: x["name"].lower())

    for r in filtered:
        place_id = r["id"]

        fav = " ❤️" if r.get("favorite") else ""
        vis = " ✅" if r.get("visited") else ""

        with st.expander(f"{r['name']}{fav}{vis} • {r['cuisine']} • {r['location']}"):
            col1, col2 = st.columns(2)

            with col1:
                if st.button(
                    "❤️ Favorite" if not r.get("favorite") else "💔 Unfavorite",
                    key=f"fav_{place_id}",
                    use_container_width=True
                ):
                    toggle_favorite_by_id(place_id)

            with col2:
                if st.button(
                    "✅ Mark Visited" if not r.get("visited") else "❌ Mark Unvisited",
                    key=f"vis_{place_id}",
                    use_container_width=True
                ):
                    toggle_visited_by_id(place_id)

            st.write(f"**Address:** {r.get('address','')}")
            st.markdown(f"[📍 Open in Google Maps]({google_maps_link(r.get('address',''), r['name'])})")

# ==================== ADD PLACE ====================
elif action == "Add a Place":
    st.header("Add a Place")
    with st.form("add"):
        name = st.text_input("Name")
        cuisine = st.text_input("Cuisine")
        price = st.selectbox("Price", ["$", "$$", "$$$"])
        location = st.text_input("Location")
        address = st.text_input("Address")

        if st.form_submit_button("Add"):
            supabase.table("restaurants").insert({
                "name": name,
                "cuisine": cuisine,
                "price": price,
                "location": location,
                "address": address,
                "favorite": False,
                "visited": False,
                "reviews": [],
                "images": []
            }).execute()

            st.session_state.restaurants = load_data()
            st.success("Added!")
            st.rerun()

# ==================== RANDOM PICK ====================
else:
    st.header("Random Pick 🎲")

    if not restaurants:
        st.info("Add places first")
    else:
        picked = random.choice(restaurants)
        place_id = picked["id"]

        st.subheader(picked["name"])
        st.write(picked["cuisine"], picked["location"])

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "❤️ Favorite" if not picked.get("favorite") else "💔 Unfavorite",
                key=f"rand_fav_{place_id}"
            ):
                toggle_favorite_by_id(place_id)

        with col2:
            if st.button(
                "✅ Mark Visited" if not picked.get("visited") else "❌ Mark Unvisited",
                key=f"rand_vis_{place_id}"
            ):
                toggle_visited_by_id(place_id)
