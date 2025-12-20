import streamlit as st
import json
import os
import random
import urllib.parse
import uuid
from datetime import datetime
import zipfile
from io import BytesIO

DATA_FILE = "restaurants.json"
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

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

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for place in data:
                    if "favorite" not in place: place["favorite"] = False
                    if "visited" not in place: place["visited"] = False
                    if "photos" not in place: place["photos"] = []
                    if "reviews" not in place: place["reviews"] = []
                    if "added_date" not in place: place["added_date"] = datetime.now().isoformat()
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

st.markdown("<h1 style='text-align: center;'>🍽️ Chicago Restaurant/Bar Randomizer</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Add, favorite, and randomly pick Chicago eats & drinks! 🍸</p>", unsafe_allow_html=True)

st.sidebar.header("Actions")
action = st.sidebar.radio("What do you want to do?", ["View All Places", "Add a Place", "Random Pick (with filters)"])

st.sidebar.markdown("---")

with st.sidebar.expander("⚙️ Data Management"):
    if st.button("Download backup (JSON + Images)"):
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            if os.path.exists(DATA_FILE):
                zip_file.write(DATA_FILE, os.path.basename(DATA_FILE))
            else:
                empty_data = []
                json_bytes = json.dumps(empty_data, indent=4).encode('utf-8')
                zip_file.writestr(os.path.basename(DATA_FILE), json_bytes)
            if os.path.exists(IMAGES_DIR):
                for root, _, files in os.walk(IMAGES_DIR):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=os.path.dirname(IMAGES_DIR))
                        zip_file.write(file_path, arcname)
        zip_buffer.seek(0)
        st.download_button("📥 Download full backup (ZIP)", zip_buffer.getvalue(),
                           f"chicago_restaurants_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip", "application/zip")
    uploaded_backup = st.file_uploader("Restore from backup (ZIP or JSON)", type=["json", "zip"], key="backup_uploader")
    if uploaded_backup and st.button("Restore Backup", type="primary"):
        try:
            if uploaded_backup.type == "application/zip" or uploaded_backup.name.endswith(".zip"):
                with zipfile.ZipFile(uploaded_backup, "r") as zip_file:
                    for name in zip_file.namelist():
                        if os.path.basename(name) == os.path.basename(DATA_FILE):
                            data = json.loads(zip_file.read(name))
                            save_data(data)
                            st.session_state.restaurants = data
                            break
                    for name in zip_file.namelist():
                        if name.startswith("images/") or name.startswith(IMAGES_DIR + "/"):
                            target_path = os.path.join(IMAGES_DIR, os.path.basename(name))
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, "wb") as f:
                                f.write(zip_file.read(name))
                st.success("Full backup restored!")
                st.balloons()
            else:
                data = json.load(uploaded_backup)
                save_data(data)
                st.session_state.restaurants = data
                st.success("JSON restored!")
                st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"Error: {str(e)}")

st.sidebar.caption("Built by Alan, made for us ❤️")

def delete_restaurant(index):
    r = restaurants[index]
    if r.get("photos"):
        for p in r["photos"]:
            if os.path.exists(p): os.remove(p)
    del restaurants[index]
    save_data(restaurants)
    st.success(f"{r['name']} deleted!")
    st.balloons()
    st.rerun()

def toggle_favorite(idx):
    restaurants[idx]["favorite"] = not restaurants[idx].get("favorite", False)
    save_data(restaurants)

def toggle_visited(idx):
    restaurants[idx]["visited"] = not restaurants[idx].get("visited", False)
    save_data(restaurants)

def google_maps_link(address, name=""):
    query = f"{name}, {address}" if name else address
    return f"https://www.google.com/maps/search/?api
