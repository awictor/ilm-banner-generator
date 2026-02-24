"""
ILM Banner Ad Generator – slider-enabled variant

Same output as banner_engine.py but all element positions/sizes are
parameterized for interactive adjustment via Streamlit sliders.
Imports helpers from the original engine so nothing is duplicated.
"""

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from banner_engine import (
    hex_to_rgb, trim_transparent, fit_image, paste_with_alpha,
    draw_underlined, TEXT_COLOR, CTA_COLOR, PLACEMENT,
    FONT_BOLD, FONT_REGULAR, LARGE_SIZES, _sanitize_filename,
)

# ── Default layout values (match current banner_engine.py) ───────

DEFAULT_HEADLINE_LAYOUT = {
    "logo_left_pct": 1.0,
    "logo_right_pct": 14.0,
    "hl_left_pct": 18.0,
    "hl_right_pct": 55.0,
    "prod_center_pct": 66.5,
    "prod_width_pct": 15.0,
    "cta_left_pct": 78.0,
    "pad_pct": 14.0,
    "logo_scale": 100,
    "prod_scale": 100,
}

DEFAULT_COMPACT_LAYOUT = {
    "logo_left_pct": 1.0,
    "logo_right_pct": 26.0,
    "prod_center_pct": 45.0,
    "prod_width_pct": 24.0,
    "cta_left_pct": 64.0,
    "pad_pct": 14.0,
    "logo_scale": 100,
    "prod_scale": 100,
}


# ── Banner builders (parameterized) ─────────────────────────────

def _build_headline_banner(w, h, cfg, lang, layout=None):
    """Full layout with slider-controlled positions."""
    if layout is None:
        layout = DEFAULT_HEADLINE_LAYOUT

    bg = hex_to_rgb(cfg["bg_color_hex"])
    txt = hex_to_rgb(TEXT_COLOR)
    cta_col = hex_to_rgb(CTA_COLOR)

    banner = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(banner)

    pad = max(int(h * layout["pad_pct"] / 100), 8)

    logo_l = max(int(w * layout["logo_left_pct"] / 100), pad)
    logo_r = int(w * layout["logo_right_pct"] / 100)
    hl_l = int(w * layout["hl_left_pct"] / 100)
    hl_r = int(w * layout["hl_right_pct"] / 100)
    cta_l = int(w * layout["cta_left_pct"] / 100)
    cta_r = w - pad

    prod_center = int(w * layout["prod_center_pct"] / 100)
    prod_half = int(w * layout["prod_width_pct"] / 100 / 2)
    prod_l = prod_center - prod_half
    prod_r = prod_center + prod_half

    logo_scale = layout["logo_scale"] / 100
    prod_scale = layout["prod_scale"] / 100

    noa_font = ImageFont.truetype(FONT_BOLD, max(int(h * 0.19), 10))
    cta_font = ImageFont.truetype(FONT_REGULAR, max(int(h * 0.24), 12))

    hl_zone_w = hl_r - hl_l
    if lang == "ENG":
        hl_txt = cfg["headline_eng"]
    elif lang == "FRA":
        hl_txt = cfg.get("headline_fra", cfg.get("headline_esp", ""))
    else:
        hl_txt = cfg.get("headline_esp", cfg.get("headline_fra", ""))
    hl_size = max(int(h * 0.40), 16)
    while hl_size > 8:
        hl_font = ImageFont.truetype(FONT_BOLD, hl_size)
        tw = draw.textbbox((0, 0), hl_txt, font=hl_font)[2]
        if tw <= hl_zone_w:
            break
        hl_size -= 1

    # Logo
    logo = cfg["logo_image"].convert("RGBA")
    logo = trim_transparent(logo)
    max_logo_w = max(1, int((logo_r - logo_l) * logo_scale))
    max_logo_h = max(1, int((h - pad * 2) * logo_scale))
    logo = fit_image(logo, max_logo_w, max_logo_h)
    logo_x = logo_l + (logo_r - logo_l - logo.width) // 2
    paste_with_alpha(banner, logo, (logo_x, (h - logo.height) // 2))

    # "New on Amazon!" + headline
    if lang == "ENG":
        noa_txt = "New on Amazon!"
    elif lang == "FRA":
        noa_txt = "Nouveau sur Amazon!"
    else:
        noa_txt = "\u00a1Nuevo en Amazon!"
    noa_bb = draw.textbbox((0, 0), noa_txt, font=noa_font)
    hl_bb = draw.textbbox((0, 0), hl_txt, font=hl_font)
    noa_h = noa_bb[3] - noa_bb[1]
    hl_h = hl_bb[3] - hl_bb[1]
    gap = max(int(h * 0.02), 1)
    block = noa_h + gap + hl_h
    top_y = (h - block) // 2
    draw.text((hl_l, top_y), noa_txt, font=noa_font, fill=txt)
    draw.text((hl_l, top_y + noa_h + gap), hl_txt, font=hl_font, fill=txt)

    # Product image
    prod = cfg["product_image"].convert("RGBA")
    prod = trim_transparent(prod)
    max_prod_w = max(1, int((prod_r - prod_l) * prod_scale))
    max_prod_h = max(1, int((h - 4) * prod_scale))
    prod = fit_image(prod, max_prod_w, max_prod_h)
    px = prod_center - prod.width // 2
    paste_with_alpha(banner, prod, (px, (h - prod.height) // 2))

    # CTA
    draw = ImageDraw.Draw(banner)
    if lang == "ENG":
        cta_txt = f"Shop {cfg['brand_name']}"
    elif lang == "FRA":
        cta_txt = f"Magasiner {cfg['brand_name']}"
    else:
        cta_txt = f"Compra {cfg['brand_name']}"
    cta_bb = draw.textbbox((0, 0), cta_txt, font=cta_font)
    cw = cta_bb[2] - cta_bb[0]
    ch = cta_bb[3] - cta_bb[1]
    cx = cta_l + (cta_r - cta_l - cw) // 2 - cta_bb[0]
    cy = (h - ch) // 2 - cta_bb[1]
    draw_underlined(draw, cx, cy, cta_txt, cta_font, cta_col)

    return banner


def _build_compact_banner(w, h, cfg, lang, layout=None):
    """Compact layout with slider-controlled positions."""
    if layout is None:
        layout = DEFAULT_COMPACT_LAYOUT

    bg = hex_to_rgb(cfg["bg_color_hex"])
    cta_col = hex_to_rgb(CTA_COLOR)

    banner = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(banner)

    pad = max(int(h * layout["pad_pct"] / 100), 8)

    logo_l = max(int(w * layout["logo_left_pct"] / 100), pad)
    logo_r = int(w * layout["logo_right_pct"] / 100)
    cta_l = int(w * layout["cta_left_pct"] / 100)
    cta_r = w - pad

    prod_center = int(w * layout["prod_center_pct"] / 100)
    prod_half = int(w * layout["prod_width_pct"] / 100 / 2)
    prod_l = prod_center - prod_half
    prod_r = prod_center + prod_half

    logo_scale = layout["logo_scale"] / 100
    prod_scale = layout["prod_scale"] / 100

    cta_font = ImageFont.truetype(FONT_REGULAR, max(int(h * 0.24), 12))

    # Logo
    logo = cfg["logo_image"].convert("RGBA")
    logo = trim_transparent(logo)
    max_logo_w = max(1, int((logo_r - logo_l) * logo_scale))
    max_logo_h = max(1, int((h - pad * 2) * logo_scale))
    logo = fit_image(logo, max_logo_w, max_logo_h)
    logo_x = logo_l + (logo_r - logo_l - logo.width) // 2
    paste_with_alpha(banner, logo, (logo_x, (h - logo.height) // 2))

    # Product image
    prod = cfg["product_image"].convert("RGBA")
    prod = trim_transparent(prod)
    max_prod_w = max(1, int((prod_r - prod_l) * prod_scale))
    max_prod_h = max(1, int((h - 4) * prod_scale))
    prod = fit_image(prod, max_prod_w, max_prod_h)
    px = prod_center - prod.width // 2
    paste_with_alpha(banner, prod, (px, (h - prod.height) // 2))

    # CTA
    draw = ImageDraw.Draw(banner)
    if lang == "ENG":
        cta_txt = f"Shop {cfg['brand_name']}"
    elif lang == "FRA":
        cta_txt = f"Magasiner {cfg['brand_name']}"
    else:
        cta_txt = f"Compra {cfg['brand_name']}"
    cta_bb = draw.textbbox((0, 0), cta_txt, font=cta_font)
    cw = cta_bb[2] - cta_bb[0]
    ch = cta_bb[3] - cta_bb[1]
    cx = cta_l + (cta_r - cta_l - cw) // 2 - cta_bb[0]
    cy = (h - ch) // 2 - cta_bb[1]
    draw_underlined(draw, cx, cy, cta_txt, cta_font, cta_col)

    return banner


def _build_hqp(cfg):
    """75x75 square — no slider controls needed."""
    bg = hex_to_rgb(cfg["bg_color_hex"])
    banner = Image.new("RGB", (75, 75), bg)
    prod = cfg["product_image"].convert("RGBA")
    prod = trim_transparent(prod)
    pad = 4
    prod = fit_image(prod, 75 - pad * 2, 75 - pad * 2)
    px = (75 - prod.width) // 2
    py = (75 - prod.height) // 2
    paste_with_alpha(banner, prod, (px, py))
    return banner


# ── Public API ───────────────────────────────────────────────────

def generate_all(cfg, region="US", hl_layout=None, compact_layout=None):
    """Create all banners with slider-controlled layouts.

    hl_layout:      dict of overrides for headline banners (1300x90, 1200x90)
    compact_layout: dict of overrides for compact banners (640x90)
    """
    results = []
    brand_tag = (
        _sanitize_filename(cfg['brand_name']) if region == "CA"
        else cfg['brand_abbrev']
    )

    # HQP (75x75 product thumbnail)
    hqp = _build_hqp(cfg)
    if region == "CA":
        hqp_name = f"75x75_{PLACEMENT}_{brand_tag}_CA.jpg"
    else:
        hqp_name = f"75x75_HQP_{brand_tag}.jpg"
    hqp_buf = BytesIO()
    hqp.save(hqp_buf, "JPEG", quality=95)
    hqp_buf.seek(0)
    results.append((hqp_name, hqp_buf))

    languages = ("ENG", "FRA") if region == "CA" else ("ENG", "ESP")
    for lang in languages:
        for w, h, has_hl in LARGE_SIZES:
            if has_hl:
                banner = _build_headline_banner(w, h, cfg, lang, layout=hl_layout)
            else:
                banner = _build_compact_banner(w, h, cfg, lang, layout=compact_layout)

            # Full-size
            if region == "CA":
                name = f"{w}x{h}_{PLACEMENT}_{brand_tag}_CA_{lang}.jpg"
            else:
                name = f"{w}x{h}_{lang}_{PLACEMENT}_{brand_tag}.jpg"
            buf = BytesIO()
            banner.save(buf, "JPEG", quality=95)
            buf.seek(0)
            results.append((name, buf))

            # Half-size
            hw, hh = w // 2, h // 2
            half = banner.resize((hw, hh), Image.LANCZOS)
            if region == "CA":
                hname = f"{hw}x{hh}_{PLACEMENT}_{brand_tag}_CA_{lang}.jpg"
            else:
                hname = f"{hw}x{hh}_{lang}_{PLACEMENT}_{brand_tag}.jpg"
            hbuf = BytesIO()
            half.save(hbuf, "JPEG", quality=95)
            hbuf.seek(0)
            results.append((hname, hbuf))

    return results
