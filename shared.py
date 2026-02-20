"""
Shared utilities used across multiple pages in the ILM tools app.
"""

import os
from io import BytesIO

import requests
import streamlit as st
from PIL import Image


BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")


# ── Image search helpers ────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _search_brave(query, max_results=12):
    """Image search via Brave Search API."""
    resp = requests.get(
        "https://api.search.brave.com/res/v1/images/search",
        params={"q": query, "count": min(max_results, 20)},
        headers={"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    return [
        {
            "title": r.get("title", ""),
            "image": r.get("properties", {}).get("url", r.get("url", "")),
            "thumbnail": r.get("thumbnail", {}).get("src", ""),
        }
        for r in resp.json().get("results", [])
    ]


@st.cache_data(ttl=300, show_spinner=False)
def _search_ddg(query, max_results=12):
    """Image search via DuckDuckGo (works locally, blocked on cloud IPs)."""
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        return list(ddgs.images(query, max_results=max_results))


def search_images(query, max_results=12):
    """Try Brave API first (works on AWS), fall back to DuckDuckGo (works locally)."""
    if BRAVE_API_KEY:
        try:
            return _search_brave(query, max_results)
        except Exception as e:
            st.warning(f"Brave search failed: {e}. Trying DuckDuckGo...")
    try:
        return _search_ddg(query, max_results)
    except Exception as e:
        st.error(f"Image search failed: {e}")
        return []


def remove_background(img):
    """Remove background from image using InSPyReNet (transparent-background)."""
    from transparent_background import Remover
    remover = Remover()
    img_rgb = img.convert("RGB")
    result = remover.process(img_rgb, type="rgba")
    return result.convert("RGBA")


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
        remove_bg = st.toggle("Remove background", key=f"{key_prefix}_rembg")
        if remove_bg:
            with st.spinner("Removing background..."):
                img = remove_background(img)
        st.image(img, caption=f"{label} preview", width=200)

    return img
