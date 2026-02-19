"""
ILM Banner Ad Generator – engine module

Generates banner ads in 6 sizes x 2 languages (English/Spanish) = 12 assets per brand.

Sizes generated:
  1300x90  + 650x45  (scaled down)
  1200x90  + 600x45  (scaled down)
  640x90   + 320x45  (scaled down)

Config dict expected keys:
  brand_name      str
  brand_abbrev    str
  logo_image      PIL.Image (RGBA)
  product_image   PIL.Image (RGBA)
  headline_eng    str
  headline_esp    str
  bg_color_hex    str  e.g. "#d9f69e"
"""

import os
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ── Style constants ──────────────────────────────────────────────
TEXT_COLOR = "#000000"
CTA_COLOR = "#000000"
PLACEMENT = "ILM"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_BOLD = os.path.join(
    _SCRIPT_DIR, "Fonts", "EmberModernDisplay", "EmberModernDisplayV1.1-Bold.otf"
)
FONT_REGULAR = os.path.join(
    _SCRIPT_DIR, "Fonts", "EmberModernDisplay", "EmberModernDisplayV1.1-Regular.otf"
)

LARGE_SIZES = [
    # (width, height, show_headline)
    (1300, 90, True),
    (1200, 90, True),
    (640, 90, False),
]


# ── Helpers ──────────────────────────────────────────────────────

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def remove_white_bg(img, threshold=230):
    """Replace white/near-white pixels with transparency."""
    img = img.convert("RGBA")
    data = np.array(img)
    white_mask = (
        (data[:, :, 0] > threshold)
        & (data[:, :, 1] > threshold)
        & (data[:, :, 2] > threshold)
    )
    data[white_mask, 3] = 0
    return Image.fromarray(data)


def trim_transparent(img):
    """Crop away transparent/white border pixels."""
    img = img.convert("RGBA")
    data = np.array(img)
    alpha_mask = data[:, :, 3] > 10
    color_mask = ~(
        (data[:, :, 0] > 240) & (data[:, :, 1] > 240) & (data[:, :, 2] > 240)
    )
    content = alpha_mask & color_mask
    if not content.any():
        return img
    rows = np.any(content, axis=1)
    cols = np.any(content, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    return img.crop((int(cmin), int(rmin), int(cmax) + 1, int(rmax) + 1))


def fit_image(img, max_w, max_h):
    """Resize to fit inside max_w x max_h, keeping aspect ratio."""
    ratio = min(max_w / img.width, max_h / img.height)
    new_w = max(1, int(img.width * ratio))
    new_h = max(1, int(img.height * ratio))
    return img.resize((new_w, new_h), Image.LANCZOS)


def paste_with_alpha(canvas, img, pos):
    if img.mode == "RGBA":
        canvas.paste(img, pos, img)
    else:
        canvas.paste(img, pos)


def draw_underlined(draw, x, y, text, font, colour):
    draw.text((x, y), text, font=font, fill=colour)
    bb = draw.textbbox((x, y), text, font=font)
    ul_y = bb[3] + 1
    draw.line([(bb[0], ul_y), (bb[2], ul_y)], fill=colour, width=1)


# ── Banner builders ──────────────────────────────────────────────

def _build_headline_banner(w, h, cfg, lang):
    """Full layout (1300x90 / 1200x90):
    [ Logo ]  [ 'New on Amazon!' + Headline ]  [ Product ]  [ CTA ]
    """
    bg = hex_to_rgb(cfg["bg_color_hex"])
    txt = hex_to_rgb(TEXT_COLOR)
    cta = hex_to_rgb(CTA_COLOR)

    banner = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(banner)

    pad = max(int(h * 0.14), 8)

    logo_l = pad
    logo_r = int(w * 0.16)
    hl_l = int(w * 0.17)
    hl_r = int(w * 0.62)
    prod_l = int(w * 0.62)
    prod_r = int(w * 0.77)
    cta_l = int(w * 0.78)
    cta_r = w - pad

    noa_font = ImageFont.truetype(FONT_BOLD, max(int(h * 0.19), 10))
    cta_font = ImageFont.truetype(FONT_REGULAR, max(int(h * 0.24), 12))

    hl_zone_w = hl_r - hl_l
    hl_txt = cfg["headline_eng"] if lang == "ENG" else cfg["headline_esp"]
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
    logo = fit_image(logo, logo_r - logo_l, h - pad * 2)
    paste_with_alpha(banner, logo, (logo_l, (h - logo.height) // 2))

    # "New on Amazon!" + headline
    noa_txt = "New on Amazon!" if lang == "ENG" else "\u00a1Nuevo en Amazon!"
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
    prod = fit_image(prod, prod_r - prod_l, h - 4)
    px = prod_l + (prod_r - prod_l - prod.width) // 2
    paste_with_alpha(banner, prod, (px, (h - prod.height) // 2))

    # CTA
    draw = ImageDraw.Draw(banner)
    cta_txt = (
        f"Shop {cfg['brand_name']}" if lang == "ENG"
        else f"Compra {cfg['brand_name']}"
    )
    cta_bb = draw.textbbox((0, 0), cta_txt, font=cta_font)
    cw = cta_bb[2] - cta_bb[0]
    ch = cta_bb[3] - cta_bb[1]
    cx = cta_l + (cta_r - cta_l - cw) // 2 - cta_bb[0]
    cy = (h - ch) // 2 - cta_bb[1]
    draw_underlined(draw, cx, cy, cta_txt, cta_font, cta)

    return banner


def _build_compact_banner(w, h, cfg, lang):
    """Compact layout (640x90):
    [ Logo ]  [ Product ]  [ CTA ]
    """
    bg = hex_to_rgb(cfg["bg_color_hex"])
    cta = hex_to_rgb(CTA_COLOR)

    banner = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(banner)

    pad = max(int(h * 0.14), 8)

    logo_l = pad
    logo_r = int(w * 0.28)
    prod_l = int(w * 0.29)
    prod_r = int(w * 0.52)
    cta_l = int(w * 0.54)
    cta_r = w - pad

    cta_font = ImageFont.truetype(FONT_REGULAR, max(int(h * 0.24), 12))

    # Logo
    logo = cfg["logo_image"].convert("RGBA")
    logo = trim_transparent(logo)
    logo = fit_image(logo, logo_r - logo_l, h - pad * 2)
    paste_with_alpha(banner, logo, (logo_l, (h - logo.height) // 2))

    # Product image
    prod = cfg["product_image"].convert("RGBA")
    prod = trim_transparent(prod)
    prod = fit_image(prod, prod_r - prod_l, h - 4)
    px = prod_l + (prod_r - prod_l - prod.width) // 2
    paste_with_alpha(banner, prod, (px, (h - prod.height) // 2))

    # CTA
    draw = ImageDraw.Draw(banner)
    cta_txt = (
        f"Shop {cfg['brand_name']}" if lang == "ENG"
        else f"Compra {cfg['brand_name']}"
    )
    cta_bb = draw.textbbox((0, 0), cta_txt, font=cta_font)
    cw = cta_bb[2] - cta_bb[0]
    ch = cta_bb[3] - cta_bb[1]
    cx = cta_l + (cta_r - cta_l - cw) // 2 - cta_bb[0]
    cy = (h - ch) // 2 - cta_bb[1]
    draw_underlined(draw, cx, cy, cta_txt, cta_font, cta)

    return banner


# ── Public API ───────────────────────────────────────────────────

def generate_all(cfg):
    """Create all 12 banners and return as list of (filename, BytesIO) tuples."""
    results = []

    for lang in ("ENG", "ESP"):
        for w, h, has_hl in LARGE_SIZES:
            if has_hl:
                banner = _build_headline_banner(w, h, cfg, lang)
            else:
                banner = _build_compact_banner(w, h, cfg, lang)

            # Full-size
            name = f"{w}x{h}_{lang}_{PLACEMENT}_{cfg['brand_abbrev']}.jpg"
            buf = BytesIO()
            banner.save(buf, "JPEG", quality=95)
            buf.seek(0)
            results.append((name, buf))

            # Half-size
            hw, hh = w // 2, h // 2
            half = banner.resize((hw, hh), Image.LANCZOS)
            hname = f"{hw}x{hh}_{lang}_{PLACEMENT}_{cfg['brand_abbrev']}.jpg"
            hbuf = BytesIO()
            half.save(hbuf, "JPEG", quality=95)
            hbuf.seek(0)
            results.append((hname, hbuf))

    return results
