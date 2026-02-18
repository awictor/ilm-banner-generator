"""
ILM Banner Generator – Streamlit web application
"""

import os
import time
import zipfile
from io import BytesIO

import requests
import streamlit as st
from duckduckgo_search import DDGS
from PIL import Image

import banner_engine

# ── Page config ──────────────────────────────────────────────────
st.set_page_config(page_title="ILM Banner Generator", layout="wide")

# ── Password gate ────────────────────────────────────────────────
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

if APP_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("ILM Banner Generator")
        pwd = st.text_input("Enter team password", type="password")
        if pwd:
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()

# ── Image search helper ─────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def search_images(query, max_results=12):
    """Search for images using DuckDuckGo with retry logic.
    Returns list of dicts with 'title', 'image', and 'thumbnail' keys."""
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.images(query, max_results=max_results))
            return results
        except Exception as e:
            if attempt < 2 and "403" in str(e):
                time.sleep(2 ** (attempt + 1))  # 2s, 4s backoff
                continue
            st.error(f"Image search failed: {e}")
            return []
    return []


def fetch_image_from_url(url):
    """Download an image from a URL and return a PIL Image, or None on failure."""
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))
    except Exception as e:
        st.error(f"Failed to download image: {e}")
        return None


def image_picker(label, key_prefix):
    """Widget that lets the user upload a file, paste a URL, or search the web.
    Returns a PIL Image or None."""

    tab_upload, tab_url, tab_search = st.tabs(["Upload", "Paste URL", "Search Web"])

    img = None

    with tab_upload:
        uploaded = st.file_uploader(f"Upload {label}", type=["png", "jpg", "jpeg", "webp"], key=f"{key_prefix}_upload")
        if uploaded:
            img = Image.open(uploaded)

    with tab_url:
        url = st.text_input(f"Image URL for {label}", key=f"{key_prefix}_url")
        if url:
            img = fetch_image_from_url(url)

    with tab_search:
        query = st.text_input(f"Search for {label}", key=f"{key_prefix}_search_q")
        if query:
            with st.spinner("Searching..."):
                results = search_images(query)
            if results:
                cols = st.columns(4)
                for i, r in enumerate(results):
                    with cols[i % 4]:
                        thumb_url = r.get("thumbnail") or r.get("image", "")
                        st.image(thumb_url, use_container_width=True)
                        if st.button("Use this", key=f"{key_prefix}_pick_{i}"):
                            picked = fetch_image_from_url(r["image"])
                            if picked:
                                st.session_state[f"{key_prefix}_picked"] = picked
                                st.rerun()

        if f"{key_prefix}_picked" in st.session_state:
            img = st.session_state[f"{key_prefix}_picked"]

    if img:
        st.image(img, caption=f"{label} preview", width=200)

    return img


# ── Main UI ──────────────────────────────────────────────────────
st.title("ILM Banner Generator")

left, right = st.columns(2)

with left:
    st.subheader("Logo")
    logo_img = image_picker("brand logo (PNG)", "logo")

    st.subheader("Product Image")
    product_img = image_picker("product image (PNG)", "product")

with right:
    st.subheader("Brand Details")
    brand_name = st.text_input("Brand name", placeholder="e.g. OC Integrative Medicine")
    brand_abbrev = st.text_input("Brand abbreviation", placeholder="e.g. OCIM")
    headline_eng = st.text_input("English headline", placeholder="e.g. Motility Activator by Dr. Rajsree")
    headline_esp = st.text_input("Spanish headline", placeholder="e.g. Activador de la motilidad de Dr. Rajsree")
    bg_color = st.color_picker("Background color", value="#d9f69e")

st.divider()

# ── Generate ─────────────────────────────────────────────────────
ready = (logo_img is not None
         and product_img is not None
         and brand_name
         and brand_abbrev
         and headline_eng
         and headline_esp)

if st.button("Generate Banners", type="primary", disabled=not ready):
    cfg = {
        "brand_name": brand_name,
        "brand_abbrev": brand_abbrev,
        "logo_image": logo_img,
        "product_image": product_img,
        "headline_eng": headline_eng,
        "headline_esp": headline_esp,
        "bg_color_hex": bg_color,
    }

    with st.spinner("Generating 12 banners..."):
        results = banner_engine.generate_all(cfg)

    st.success(f"Generated {len(results)} banners!")

    # Preview the 6 large banners
    st.subheader("Preview (large sizes)")
    for name, buf in results:
        # Show only the large sizes in preview
        w = int(name.split("x")[0])
        if w >= 640:
            st.caption(name)
            buf.seek(0)
            st.image(buf, use_container_width=True)

    # ZIP download
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, buf in results:
            buf.seek(0)
            zf.writestr(name, buf.read())
    zip_buf.seek(0)

    st.download_button(
        label="Download All (ZIP)",
        data=zip_buf,
        file_name=f"ILM_{brand_abbrev}_Banners.zip",
        mime="application/zip",
        type="primary",
    )
