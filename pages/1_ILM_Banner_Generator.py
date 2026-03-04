"""
ILM Banner Generator – page UI (moved from app.py)
"""

import zipfile
from io import BytesIO

import streamlit as st

import banner_engine
from shared import image_picker, show_offline_banner

# ── Main UI ──────────────────────────────────────────────────────
show_offline_banner()
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

    st.markdown("**Text Colors**")
    _presets = {"Black": "#000000", "White": "#FFFFFF", "Navy": "#1B2A4A", "Dark Gray": "#333333"}
    tc1, tc2 = st.columns(2)
    with tc1:
        hl_preset = st.selectbox("Headline preset", list(_presets.keys()) + ["Custom"], key="hl_preset")
        if hl_preset == "Custom":
            text_color = st.color_picker("Headline color", value="#000000", key="hl_color")
        else:
            text_color = _presets[hl_preset]
    with tc2:
        cta_preset = st.selectbox("CTA preset", list(_presets.keys()) + ["Custom"], key="cta_preset")
        if cta_preset == "Custom":
            cta_color = st.color_picker("CTA color", value="#000000", key="cta_color")
        else:
            cta_color = _presets[cta_preset]

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
        "text_color_hex": text_color,
        "cta_color_hex": cta_color,
    }

    with st.spinner("Generating 12 banners..."):
        results = banner_engine.generate_all(cfg)

    st.success(f"Generated {len(results)} banners!")

    # Preview all banners
    st.subheader("Preview")
    for name, buf in results:
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
