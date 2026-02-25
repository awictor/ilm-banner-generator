"""
Just Dropped — Simulator

Quick-fire tool to generate and preview Just Dropped Instagram Story frames.
No wizard steps — just pick a channel, add products, and generate.
"""

import zipfile
from io import BytesIO

import streamlit as st
from PIL import Image

import story_engine
from shared import image_picker, remove_background, show_offline_banner

CHANNELS = [
    "@AmazonHome",
    "@AmazonBeauty",
    "@AmazonFashion",
    "@Amazon",
    "@Amazon.ca",
]

show_offline_banner()
st.title("Just Dropped — Simulator")
st.caption("Quick preview tool. Add products, pick a channel, generate frames.")

# ── Settings ──────────────────────────────────────────────────────
st.subheader("Settings")
col_ch, col_theme = st.columns(2)
with col_ch:
    channel = st.selectbox("Channel", CHANNELS, key="sim_channel")
with col_theme:
    theme_name = st.text_input("Theme name", value="Just Dropped", key="sim_theme")

num_products = st.slider("Number of products", 1, 9, 4, key="sim_num_products")

st.divider()

# ── Product Entry ─────────────────────────────────────────────────
st.subheader("Products")

# Initialise session state
if "sim_products" not in st.session_state:
    st.session_state.sim_products = []

# Ensure we have enough entries
while len(st.session_state.sim_products) < num_products:
    st.session_state.sim_products.append(
        {"asin": "", "brand": "", "product_name": "", "copy": "", "image": None}
    )

products = st.session_state.sim_products

for i in range(num_products):
    with st.expander(
        f"Product {i+1}"
        + (f" — {products[i]['product_name']}" if products[i]['product_name'] else ""),
        expanded=(i < 2),
    ):
        left, right = st.columns([1, 1])
        with left:
            products[i]["asin"] = st.text_input(
                "ASIN", value=products[i]["asin"],
                key=f"sim_asin_{i}", placeholder="B0XXXXXXXXX"
            )
            products[i]["brand"] = st.text_input(
                "Brand", value=products[i]["brand"],
                key=f"sim_brand_{i}"
            )
            products[i]["product_name"] = st.text_input(
                "Product Name", value=products[i]["product_name"],
                key=f"sim_prodname_{i}"
            )
            products[i]["copy"] = st.text_area(
                "Benefit Copy", value=products[i]["copy"],
                key=f"sim_copy_{i}", height=60
            )
        with right:
            img = image_picker(
                f"product {i+1} image",
                f"sim_img_{i}",
            )
            if img:
                products[i]["image"] = img

st.session_state.sim_products = products

# ── Generate ──────────────────────────────────────────────────────
st.divider()

ready_products = [
    p for p in products[:num_products]
    if p.get("image") is not None and p.get("product_name")
]

st.metric("Products ready", f"{len(ready_products)} / {num_products}")

if st.button("Generate Frames", type="primary", disabled=len(ready_products) == 0):
    with st.spinner(f"Generating {channel} frames..."):
        frames = story_engine.generate_franchise_frames(
            channel, ready_products, theme_name
        )

    st.session_state.sim_frames = frames
    st.rerun()

# ── Preview ───────────────────────────────────────────────────────
if "sim_frames" in st.session_state and st.session_state.sim_frames:
    frames = st.session_state.sim_frames
    st.success(f"Generated {len(frames)} frames!")

    # Show as horizontal scrollable strip
    st.subheader("Preview")

    # Group EN / FR for Amazon.ca
    if channel == "@Amazon.ca":
        en_frames = [(f, b) for f, b in frames if "_FR/" not in f]
        fr_frames = [(f, b) for f, b in frames if "_FR/" in f]

        st.markdown("**English**")
        cols = st.columns(min(len(en_frames), 6))
        for idx, (fname, buf) in enumerate(en_frames):
            with cols[idx % len(cols)]:
                buf.seek(0)
                st.image(buf, caption=fname.split("/")[-1], width=150)

        st.markdown("**French**")
        cols = st.columns(min(len(fr_frames), 6))
        for idx, (fname, buf) in enumerate(fr_frames):
            with cols[idx % len(cols)]:
                buf.seek(0)
                st.image(buf, caption=fname.split("/")[-1], width=150)
    else:
        cols = st.columns(min(len(frames), 6))
        for idx, (fname, buf) in enumerate(frames):
            with cols[idx % len(cols)]:
                buf.seek(0)
                st.image(buf, caption=fname.split("/")[-1], width=150)

    # Full-size viewer
    st.divider()
    st.subheader("Full-Size Viewer")
    frame_names = [f for f, _ in frames]
    selected = st.selectbox("Select frame", frame_names, key="sim_view_frame")
    if selected:
        for fname, buf in frames:
            if fname == selected:
                buf.seek(0)
                st.image(buf, width=360)
                break

    # Download ZIP
    st.divider()
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, buf in frames:
            buf.seek(0)
            zf.writestr(fname, buf.read())
    zip_buf.seek(0)

    safe_ch = channel.replace("@", "").replace(".", "_")
    st.download_button(
        label="Download All Frames (ZIP)",
        data=zip_buf,
        file_name=f"Just_Dropped_{safe_ch}_Frames.zip",
        mime="application/zip",
        type="primary",
    )
