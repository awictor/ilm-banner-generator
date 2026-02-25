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
from sample_products import SAMPLE_PRODUCTS
from shared import image_picker, fetch_image_from_url, remove_background, show_offline_banner

CHANNELS = [
    "@AmazonHome",
    "@AmazonBeauty",
    "@AmazonFashion",
    "@Amazon",
    "@Amazon.ca",
]

ALL_OPTION = "All Channels"

show_offline_banner()
st.title("Just Dropped — Simulator")
st.caption("Quick preview tool. Add products, pick a channel, generate frames.")

# ── Sample Library ────────────────────────────────────────────────
with st.expander("Sample Product Library — click to auto-fill slots", expanded=False):
    st.caption("Pick products to auto-fill the slots below. Image + all fields are loaded automatically.")

    # Category filter
    categories = sorted(set(p["category"] for p in SAMPLE_PRODUCTS))
    cat_filter = st.pills("Filter", ["All"] + categories, default="All", key="sim_lib_cat")

    if cat_filter and cat_filter != "All":
        filtered = [p for p in SAMPLE_PRODUCTS if p["category"] == cat_filter]
    else:
        filtered = SAMPLE_PRODUCTS

    lib_cols = st.columns(4)
    for idx, sample in enumerate(filtered):
        with lib_cols[idx % 4]:
            st.image(sample["image_url"], use_container_width=True)
            st.caption(f"**{sample['brand']}**\n{sample['product_name']}")
            if st.button("Add", key=f"lib_add_{sample['asin']}"):
                # Find the first empty slot or append
                prods = st.session_state.get("sim_products", [])
                placed = False
                for p in prods:
                    if not p.get("product_name") and p.get("image") is None:
                        p["asin"] = sample["asin"]
                        p["brand"] = sample["brand"]
                        p["product_name"] = sample["product_name"]
                        p["copy"] = sample["copy"]
                        # Download the image
                        p["image"] = fetch_image_from_url(sample["image_url"])
                        placed = True
                        break
                if not placed:
                    # All slots filled — append a new one
                    img = fetch_image_from_url(sample["image_url"])
                    prods.append({
                        "asin": sample["asin"],
                        "brand": sample["brand"],
                        "product_name": sample["product_name"],
                        "copy": sample["copy"],
                        "image": img,
                    })
                st.session_state.sim_products = prods
                st.rerun()

st.divider()

# ── Settings ──────────────────────────────────────────────────────
st.subheader("Settings")
col_ch, col_theme = st.columns(2)
with col_ch:
    channel_options = [ALL_OPTION] + CHANNELS
    selection = st.selectbox("Channel", channel_options, key="sim_channel")
with col_theme:
    theme_name = st.text_input("Theme name", value="Just Dropped", key="sim_theme")

st.subheader("Product Effects")
effect_cols = st.columns(4)
with effect_cols[0]:
    fx_shadow = st.toggle("Drop Shadow", value=True, key="fx_shadow")
    fx_outline = st.toggle("White Outline", value=True, key="fx_outline")
    fx_float = st.toggle("Float Shadow", value=False, key="fx_float",
                         help="Levitation shadow (replaces drop shadow)")
with effect_cols[1]:
    fx_glow = st.toggle("Accent Glow", value=False, key="fx_glow")
    fx_neon = st.toggle("Neon Border", value=False, key="fx_neon")
    fx_tilt = st.toggle("Subtle Tilt", value=False, key="fx_tilt")
with effect_cols[2]:
    fx_sparkles = st.toggle("Sparkles", value=False, key="fx_sparkles")
    fx_reflection = st.toggle("Reflection", value=False, key="fx_reflection")
    fx_polaroid = st.toggle("Polaroid Frame", value=False, key="fx_polaroid")
with effect_cols[3]:
    fx_noise = st.toggle("Noise/Grain", value=False, key="fx_noise")

effects = {
    "shadow": fx_shadow,
    "outline": fx_outline,
    "glow": fx_glow,
    "tilt": fx_tilt,
    "sparkles": fx_sparkles,
    "reflection": fx_reflection,
    "float_shadow": fx_float,
    "neon_border": fx_neon,
    "polaroid": fx_polaroid,
    "noise": fx_noise,
}

layout_col, num_col = st.columns(2)
with layout_col:
    layout_options = list(story_engine.COLLAGE_LAYOUTS.keys())
    layout_style = st.selectbox("Collage Layout", layout_options, key="sim_layout")
with num_col:
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
                key=f"sim_copy_{i}", height=68
            )
        with right:
            # Show pre-loaded image if it exists
            if products[i].get("image") is not None:
                st.image(products[i]["image"], caption="Loaded from library", width=200)
                col_rm, col_clr = st.columns(2)
                with col_rm:
                    if st.button("Remove BG", key=f"sim_rembg_{i}"):
                        with st.spinner("Removing background..."):
                            products[i]["image"] = remove_background(products[i]["image"])
                        st.rerun()
                with col_clr:
                    if st.button("Clear image", key=f"sim_clear_{i}"):
                        products[i]["image"] = None
                        st.rerun()
            else:
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

# Determine which channels to generate
generate_channels = CHANNELS if selection == ALL_OPTION else [selection]

if st.button("Generate Frames", type="primary", disabled=len(ready_products) == 0):
    all_frames = []
    label = "all channels" if selection == ALL_OPTION else selection
    with st.spinner(f"Generating {label} frames..."):
        for ch in generate_channels:
            frames = story_engine.generate_franchise_frames(
                ch, ready_products, theme_name, effects=effects,
                layout=layout_style
            )
            all_frames.extend(frames)

    st.session_state.sim_frames = all_frames
    st.session_state.sim_generated_selection = selection
    st.rerun()

# ── Preview ───────────────────────────────────────────────────────
if "sim_frames" in st.session_state and st.session_state.sim_frames:
    frames = st.session_state.sim_frames
    st.success(f"Generated {len(frames)} frames!")

    st.subheader("Preview")

    # Group frames by channel folder
    folders = {}
    for fname, buf in frames:
        folder = fname.split("/")[0] if "/" in fname else "Other"
        folders.setdefault(folder, []).append((fname, buf))

    # Build horizontal strip for each channel group
    def _make_strip(frame_list, card_height=800):
        """Combine frames into a horizontal strip preview."""
        scaled = []
        for _fname, _buf in frame_list:
            _buf.seek(0)
            img = Image.open(_buf).convert("RGB")
            ratio = card_height / img.height
            new_w = int(img.width * ratio)
            scaled.append(img.resize((new_w, card_height), Image.LANCZOS))
        gap = 8
        total_w = sum(s.width for s in scaled) + gap * (len(scaled) - 1)
        strip = Image.new("RGB", (total_w, card_height), (255, 255, 255))
        x = 0
        for s in scaled:
            strip.paste(s, (x, 0))
            x += s.width + gap
        return strip

    strips = {}  # folder_name -> PIL Image
    for folder in sorted(folders.keys()):
        folder_frames = folders[folder]

        # Banner strip for this channel
        strip_img = _make_strip(folder_frames)
        strips[folder] = strip_img
        st.image(strip_img, caption=f"{folder} — Story Sequence", use_container_width=True)

        # Individual frames in collapsible detail
        with st.expander(f"{folder} — individual frames ({len(folder_frames)})", expanded=False):
            cols = st.columns(min(len(folder_frames), 6))
            for idx, (fname, buf) in enumerate(folder_frames):
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

    # Download ZIP (includes strip banners)
    st.divider()
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, buf in frames:
            buf.seek(0)
            zf.writestr(fname, buf.read())
        # Add strip banners to ZIP
        for folder_name, strip_img in strips.items():
            strip_buf = BytesIO()
            strip_img.save(strip_buf, "JPEG", quality=92)
            strip_buf.seek(0)
            zf.writestr(f"{folder_name}/Story_Sequence_Banner.jpg", strip_buf.read())
    zip_buf.seek(0)

    gen_sel = st.session_state.get("sim_generated_selection", selection)
    if gen_sel == ALL_OPTION:
        zip_name = "Just_Dropped_All_Channels_Frames.zip"
    else:
        safe_ch = gen_sel.replace("@", "").replace(".", "_")
        zip_name = f"Just_Dropped_{safe_ch}_Frames.zip"

    st.download_button(
        label="Download All Frames (ZIP)",
        data=zip_buf,
        file_name=zip_name,
        mime="application/zip",
        type="primary",
    )
