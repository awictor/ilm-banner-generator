"""
ILM Banner Generator — With Sliders

Same banner generation as the standard ILM tool, but with sliders
to adjust the position and size of every element in real time.
"""

import zipfile
from io import BytesIO

import streamlit as st

import banner_engine_sliders as engine
from shared import image_picker

# ── Main UI ──────────────────────────────────────────────────────
st.title("ILM Banner Generator — With Sliders")

left, right = st.columns(2)

with left:
    st.subheader("Logo")
    logo_img = image_picker("brand logo (PNG)", "sl_logo")

    st.subheader("Product Image")
    product_img = image_picker("product image (PNG)", "sl_product")

with right:
    st.subheader("Brand Details")
    brand_name = st.text_input("Brand name", placeholder="e.g. OC Integrative Medicine", key="sl_brand_name")
    brand_abbrev = st.text_input("Brand abbreviation", placeholder="e.g. OCIM", key="sl_brand_abbrev")
    headline_eng = st.text_input("English headline", placeholder="e.g. Motility Activator by Dr. Rajsree", key="sl_hl_eng")
    headline_esp = st.text_input("Spanish headline", placeholder="e.g. Activador de la motilidad de Dr. Rajsree", key="sl_hl_esp")
    bg_color = st.color_picker("Background color", value="#d9f69e", key="sl_bg_color")

st.divider()

# ── Layout Sliders ───────────────────────────────────────────────
st.subheader("Layout Controls")

tab_hl, tab_compact = st.tabs(["Headline Banner (1300x90, 1200x90)", "Compact Banner (640x90)"])

with tab_hl:
    st.markdown("Adjust positioning for the **1300x90** and **1200x90** banners.")
    st.caption("Values are percentages of the banner width. The live preview updates as you adjust.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Logo**")
        hl_logo_left = st.slider("Left edge %", 0.0, 15.0, 1.0, 0.5, key="hl_logo_l")
        hl_logo_right = st.slider("Right edge %", 5.0, 30.0, 14.0, 0.5, key="hl_logo_r")
        hl_logo_scale = st.slider("Logo size %", 50, 150, 100, 5, key="hl_logo_s")

        st.markdown("**Headline Text**")
        hl_text_left = st.slider("Start %", 10.0, 35.0, 18.0, 0.5, key="hl_txt_l")
        hl_text_right = st.slider("End %", 30.0, 70.0, 55.0, 0.5, key="hl_txt_r")

    with c2:
        st.markdown("**Product Image**")
        hl_prod_center = st.slider("Center position %", 35.0, 85.0, 66.5, 0.5, key="hl_prod_c")
        hl_prod_width = st.slider("Width %", 5.0, 35.0, 15.0, 0.5, key="hl_prod_w")
        hl_prod_scale = st.slider("Product size %", 50, 150, 100, 5, key="hl_prod_s")

        st.markdown("**CTA (Shop link)**")
        hl_cta_left = st.slider("Start %", 55.0, 95.0, 78.0, 0.5, key="hl_cta_l")

        st.markdown("**Padding**")
        hl_pad = st.slider("Vertical padding %", 5.0, 25.0, 14.0, 0.5, key="hl_pad")

    hl_layout = {
        "logo_left_pct": hl_logo_left,
        "logo_right_pct": hl_logo_right,
        "hl_left_pct": hl_text_left,
        "hl_right_pct": hl_text_right,
        "prod_center_pct": hl_prod_center,
        "prod_width_pct": hl_prod_width,
        "cta_left_pct": hl_cta_left,
        "pad_pct": hl_pad,
        "logo_scale": hl_logo_scale,
        "prod_scale": hl_prod_scale,
    }

with tab_compact:
    st.markdown("Adjust positioning for the **640x90** banners (no headline text).")
    st.caption("Values are percentages of the banner width. The live preview updates as you adjust.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Logo**")
        cp_logo_left = st.slider("Left edge %", 0.0, 15.0, 1.0, 0.5, key="cp_logo_l")
        cp_logo_right = st.slider("Right edge %", 10.0, 45.0, 26.0, 0.5, key="cp_logo_r")
        cp_logo_scale = st.slider("Logo size %", 50, 150, 100, 5, key="cp_logo_s")

    with c2:
        st.markdown("**Product Image**")
        cp_prod_center = st.slider("Center position %", 20.0, 70.0, 45.0, 0.5, key="cp_prod_c")
        cp_prod_width = st.slider("Width %", 8.0, 40.0, 24.0, 0.5, key="cp_prod_w")
        cp_prod_scale = st.slider("Product size %", 50, 150, 100, 5, key="cp_prod_s")

        st.markdown("**CTA (Shop link)**")
        cp_cta_left = st.slider("Start %", 40.0, 90.0, 64.0, 0.5, key="cp_cta_l")

        st.markdown("**Padding**")
        cp_pad = st.slider("Vertical padding %", 5.0, 25.0, 14.0, 0.5, key="cp_pad")

    compact_layout = {
        "logo_left_pct": cp_logo_left,
        "logo_right_pct": cp_logo_right,
        "prod_center_pct": cp_prod_center,
        "prod_width_pct": cp_prod_width,
        "cta_left_pct": cp_cta_left,
        "pad_pct": cp_pad,
        "logo_scale": cp_logo_scale,
        "prod_scale": cp_prod_scale,
    }

st.divider()

# ── Live Preview ─────────────────────────────────────────────────
ready = (logo_img is not None
         and product_img is not None
         and brand_name
         and brand_abbrev
         and headline_eng
         and headline_esp)

if ready:
    cfg = {
        "brand_name": brand_name,
        "brand_abbrev": brand_abbrev,
        "logo_image": logo_img,
        "product_image": product_img,
        "headline_eng": headline_eng,
        "headline_esp": headline_esp,
        "bg_color_hex": bg_color,
    }

    st.subheader("Live Preview")
    st.caption("These update automatically as you move the sliders.")

    # Headline preview (1300x90)
    preview_hl = engine._build_headline_banner(1300, 90, cfg, "ENG", layout=hl_layout)
    st.markdown("**1300x90 — Headline**")
    st.image(preview_hl, use_container_width=True)

    # Compact preview (640x90)
    preview_cp = engine._build_compact_banner(640, 90, cfg, "ENG", layout=compact_layout)
    st.markdown("**640x90 — Compact**")
    st.image(preview_cp, use_container_width=True)

    st.divider()

    # ── Generate All ─────────────────────────────────────────────
    if st.button("Generate All Banners", type="primary"):
        with st.spinner("Generating 12 banners..."):
            results = engine.generate_all(
                cfg,
                hl_layout=hl_layout,
                compact_layout=compact_layout,
            )

        st.success(f"Generated {len(results)} banners!")

        st.subheader("All Banners")
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
else:
    st.info("Fill in all fields above to see a live preview.")
