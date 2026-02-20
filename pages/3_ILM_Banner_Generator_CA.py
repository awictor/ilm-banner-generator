"""
ILM Banner Generator – Canada
Same banners as the US tool but with CA naming convention:
  {size}_ILM_{brand_name}_CA_{lang}.jpg
"""

import zipfile
from io import BytesIO

import streamlit as st

import banner_engine
from shared import image_picker

# ── Main UI ──────────────────────────────────────────────────────
st.title("ILM Banner Generator – Canada")

left, right = st.columns(2)

with left:
    st.subheader("Logo")
    logo_img = image_picker("brand logo (PNG)", "ca_logo")

    st.subheader("Product Image")
    product_img = image_picker("product image (PNG)", "ca_product")

with right:
    st.subheader("Brand Details")
    brand_name = st.text_input("Brand name", placeholder="e.g. OC Integrative Medicine", key="ca_brand_name")
    brand_abbrev = st.text_input("Brand abbreviation", placeholder="e.g. OCIM", key="ca_brand_abbrev")
    headline_eng = st.text_input("English headline", placeholder="e.g. Motility Activator by Dr. Rajsree", key="ca_headline_eng")
    headline_esp = st.text_input("Spanish headline", placeholder="e.g. Activador de la motilidad de Dr. Rajsree", key="ca_headline_esp")
    bg_color = st.color_picker("Background color", value="#d9f69e", key="ca_bg_color")

st.divider()

# ── Generate ─────────────────────────────────────────────────────
ready = (logo_img is not None
         and product_img is not None
         and brand_name
         and brand_abbrev
         and headline_eng
         and headline_esp)

if st.button("Generate Banners", type="primary", disabled=not ready, key="ca_generate"):
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
        results = banner_engine.generate_all(cfg, region="CA")

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

    safe_name = banner_engine._sanitize_filename(brand_name)
    st.download_button(
        label="Download All (ZIP)",
        data=zip_buf,
        file_name=f"ILM_{safe_name}_CA_Banners.zip",
        mime="application/zip",
        type="primary",
        key="ca_download",
    )
