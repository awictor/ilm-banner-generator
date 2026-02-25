"""
Instagram Story Frame Generator -- engine module

Generates 1080x1920px story frames for 5 Amazon channels:
  @AmazonHome, @AmazonBeauty, @AmazonFashion, @Amazon, @Amazon.ca

Each channel has a distinct visual style matching the reference mockups.
Frame structure per franchise:
  Frame 1:    Collage (scattered products + "Just Dropped" title)
  Frames 2-N: Individual product frames (annotation + product + copy + CTA)
  Last frame: Duplicate of Frame 1
"""

import os
import random
from datetime import datetime
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from banner_engine import hex_to_rgb, remove_white_bg, trim_transparent, fit_image, paste_with_alpha

# -- Constants ----------------------------------------------------------------
W, H = 1080, 1920  # Instagram story dimensions

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DISPLAY_BOLD = os.path.join(
    _SCRIPT_DIR, "Fonts", "EmberModernDisplay", "EmberModernDisplayV1.1-Bold.otf"
)
FONT_DISPLAY_REGULAR = os.path.join(
    _SCRIPT_DIR, "Fonts", "EmberModernDisplay", "EmberModernDisplayV1.1-Regular.otf"
)
FONT_DISPLAY_ITALIC = os.path.join(
    _SCRIPT_DIR, "Fonts", "EmberModernDisplay", "EmberModernDisplayV1.1-Italic.otf"
)
FONT_TEXT_REGULAR = os.path.join(
    _SCRIPT_DIR, "Fonts", "EmberModernText", "EmberModernTextV1.1-Regular.otf"
)
FONT_TEXT_BOLD = os.path.join(
    _SCRIPT_DIR, "Fonts", "EmberModernText", "EmberModernTextV1.1-Bold.otf"
)
FONT_TEXT_ITALIC = os.path.join(
    _SCRIPT_DIR, "Fonts", "EmberModernText", "EmberModernTextV1.1-Italic.otf"
)

# Channel color palettes
PALETTE = {
    "@AmazonHome": {
        "bg": "#E8E6E0",
        "text": "#3A3A3A",
        "accent": "#8B7D6B",
        "watermark": "#DFDDDA",
    },
    "@AmazonBeauty": {
        "bg": "#D4EFE0",
        "bg_individual": "#F5F8F6",
        "circle": "#C8EDDA",
        "text": "#3A3A3A",
        "accent": "#4A8B6F",
    },
    "@AmazonFashion": {
        "bg": "#E8E6E0",
        "text": "#3A3A3A",
        "accent": "#8B7D6B",
    },
    "@Amazon": {
        "bg": "#F5E6DC",
        "text": "#3A3A3A",
        "accent": "#6B5B73",
        # Per-gradient watermark colors (barely visible, near-bg tint)
        "gradient_watermarks": [
            "#F0DDD4",  # peachy pink
            "#DDD6E8",  # lavender
            "#F5ECCC",  # yellow
            "#CCDCEB",  # blue
            "#CBE5D6",  # mint
            "#EBE7DE",  # beige
        ],
        "gradients": [
            ("#F5E6DC", "#F0D4C8"),  # peachy pink
            ("#E8E0F0", "#D8CCE8"),  # lavender
            ("#FFF5D6", "#FFEDBA"),  # yellow
            ("#D6E8F5", "#C0D8F0"),  # blue
            ("#D4EFE0", "#C0E8D0"),  # mint
            ("#F5F1ED", "#EDE5D8"),  # beige
        ],
    },
    "@Amazon.ca": {
        "bg": "#F5E6DC",
        "text": "#3A3A3A",
        "accent": "#6B5B73",
        "gradient_watermarks": [
            "#F0DDD4",
            "#DDD6E8",
            "#F5ECCC",
            "#CCDCEB",
            "#CBE5D6",
            "#EBE7DE",
        ],
        "gradients": [
            ("#F5E6DC", "#F0D4C8"),
            ("#E8E0F0", "#D8CCE8"),
            ("#FFF5D6", "#FFEDBA"),
            ("#D6E8F5", "#C0D8F0"),
            ("#D4EFE0", "#C0E8D0"),
            ("#F5F1ED", "#EDE5D8"),
        ],
    },
}


def _current_month():
    return datetime.now().strftime("%B").lower()


# -- Drawing helpers ----------------------------------------------------------

def _make_gradient(w, h, color_top, color_bottom):
    top = np.array(hex_to_rgb(color_top), dtype=np.float32)
    bot = np.array(hex_to_rgb(color_bottom), dtype=np.float32)
    t = np.linspace(0.0, 1.0, h, dtype=np.float32).reshape(h, 1, 1)
    arr = (top + (bot - top) * t).astype(np.uint8)
    arr = np.broadcast_to(arr, (h, w, 3)).copy()
    return Image.fromarray(arr, "RGB")


def _draw_text_block(draw, text, x, y, font, color, max_width=None, align="left",
                     line_spacing=8, max_lines=0):
    if not max_width:
        draw.text((x, y), text, font=font, fill=color)
        bb = draw.textbbox((x, y), text, font=font)
        return bb[3] - bb[1]

    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        tw = draw.textbbox((0, 0), test, font=font)[2]
        if tw <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    if max_lines > 0 and len(lines) > max_lines:
        last = lines[max_lines - 1]
        while last:
            candidate = last + "..."
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                break
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        lines = lines[:max_lines - 1] + [last + "..."]

    total_h = 0
    for line in lines:
        if align == "center":
            lw = draw.textbbox((0, 0), line, font=font)[2]
            lx = x + (max_width - lw) // 2
        elif align == "right":
            lw = draw.textbbox((0, 0), line, font=font)[2]
            lx = x + max_width - lw
        else:
            lx = x
        draw.text((lx, y + total_h), line, font=font, fill=color)
        line_bb = draw.textbbox((0, 0), line, font=font)
        total_h += (line_bb[3] - line_bb[1]) + line_spacing
    return total_h


def _draw_handwritten(draw, text, x, y, color, size=28):
    font = ImageFont.truetype(FONT_DISPLAY_ITALIC, size)
    draw.text((x, y), text, font=font, fill=color)
    bb = draw.textbbox((x, y), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


def _draw_watermark_pattern(draw, text, color, font_size=42, spacing_x=360, spacing_y=90):
    font = ImageFont.truetype(FONT_DISPLAY_BOLD, font_size)
    for row in range(-2, H // spacing_y + 2):
        offset_x = (row % 2) * (spacing_x // 2)
        for col in range(-1, W // spacing_x + 2):
            tx = col * spacing_x + offset_x
            ty = row * spacing_y
            draw.text((tx, ty), text, font=font, fill=color)


def _draw_cta_link(canvas, product_name, accent_color, y_pos):
    """Draw 'SHOP [PRODUCT]' CTA with link icon, centered."""
    draw = ImageDraw.Draw(canvas)
    cta_font = ImageFont.truetype(FONT_TEXT_BOLD, 22)
    cta_text = f"SHOP {product_name.upper()}"

    cta_bb = draw.textbbox((0, 0), cta_text, font=cta_font)
    cta_w = cta_bb[2] - cta_bb[0]
    icon_size = 20
    total_w = icon_size + 10 + cta_w
    start_x = (W - total_w) // 2

    # Circle with arrow icon
    cx = start_x + icon_size // 2
    cy = y_pos + icon_size // 2
    draw.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=accent_color, width=2)
    draw.line([(cx - 3, cy + 3), (cx + 4, cy - 4)], fill=accent_color, width=2)
    draw.line([(cx + 4, cy - 4), (cx - 1, cy - 4)], fill=accent_color, width=2)
    draw.line([(cx + 4, cy - 4), (cx + 4, cy + 1)], fill=accent_color, width=2)

    draw.text((start_x + icon_size + 10, y_pos - 2), cta_text,
              font=cta_font, fill=accent_color)


def _draw_benefit_and_cta(canvas, copy_text, product_name, text_color, accent_color, y_start):
    """Benefit copy (regular weight, centered) + CTA link below."""
    draw = ImageDraw.Draw(canvas)

    # Benefit copy: REGULAR weight (not bold), centered, smaller size
    if copy_text:
        copy_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)
        copy_h = _draw_text_block(
            draw, copy_text, 80, y_start,
            copy_font, text_color,
            max_width=W - 160, align="center",
            line_spacing=10, max_lines=2,
        )
    else:
        copy_h = 0

    cta_y = y_start + copy_h + 40
    if product_name:
        _draw_cta_link(canvas, product_name, accent_color, cta_y)


def _prepare_product(product_image, max_w, max_h):
    img = product_image.convert("RGBA")
    img = trim_transparent(img)
    img = fit_image(img, max_w, max_h)
    return img


def _add_drop_shadow(img, offset=(6, 6), blur_radius=12, opacity=60):
    """Add a soft drop shadow behind an RGBA image."""
    from PIL import ImageFilter
    # Create shadow layer
    shadow = Image.new("RGBA", (img.width + abs(offset[0]) + blur_radius * 2,
                                 img.height + abs(offset[1]) + blur_radius * 2),
                       (0, 0, 0, 0))
    # Paste a dark silhouette
    silhouette = Image.new("RGBA", img.size, (0, 0, 0, opacity))
    # Use the alpha channel of the original as mask
    if img.mode == "RGBA":
        silhouette.putalpha(img.split()[3])
    sx = blur_radius + max(offset[0], 0)
    sy = blur_radius + max(offset[1], 0)
    shadow.paste(silhouette, (sx, sy))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    # Paste original on top
    ox = blur_radius + max(-offset[0], 0)
    oy = blur_radius + max(-offset[1], 0)
    shadow.paste(img, (ox, oy), img)
    return shadow


def _save_frame(canvas):
    buf = BytesIO()
    canvas.save(buf, "PNG")
    buf.seek(0)
    return buf


def _pad_products(products, count):
    if not products:
        return []
    if len(products) >= count:
        return products[:count]
    return (products * ((count // len(products)) + 1))[:count]


# -- Scattered collage helper -------------------------------------------------

def _scatter_products(canvas, products, positions, circle_color=None,
                      jitter_xy=30, jitter_angle=5, jitter_scale=(0.90, 1.10),
                      shuffle=True):
    """Place products at scattered (x, y, w, h, rotation) positions with randomization.

    Each position is (x, y, w, h) or (x, y, w, h, angle).
    Products deliberately overlap and vary in size for organic editorial feel.

    Randomization per call:
      - Product-to-slot assignment is shuffled (shuffle=True)
      - Position jitter: ±jitter_xy pixels on x/y
      - Rotation jitter: ±jitter_angle degrees added to base angle
      - Size jitter: random scale factor within jitter_scale range
    """
    draw = ImageDraw.Draw(canvas)
    display = _pad_products(products, len(positions))

    # Shuffle product-to-slot mapping so each run looks different
    if shuffle:
        slot_indices = list(range(len(positions)))
        random.shuffle(slot_indices)
    else:
        slot_indices = list(range(len(positions)))

    for idx, prod_data in enumerate(display):
        slot = slot_indices[idx]
        pos = positions[slot]
        px, py, pw, ph = pos[0], pos[1], pos[2], pos[3]
        base_angle = pos[4] if len(pos) > 4 else 0

        # Apply jitter
        px += random.randint(-jitter_xy, jitter_xy)
        py += random.randint(-jitter_xy, jitter_xy)
        angle = base_angle + random.uniform(-jitter_angle, jitter_angle)
        scale = random.uniform(jitter_scale[0], jitter_scale[1])

        # Scale the cell size
        sw = int(pw * scale)
        sh = int(ph * scale)

        if circle_color:
            cr = min(sw, sh) // 2 - 10
            ccx = px + sw // 2
            ccy = py + sh // 2
            draw.ellipse([ccx - cr, ccy - cr, ccx + cr, ccy + cr],
                         fill=hex_to_rgb(circle_color))
            draw = ImageDraw.Draw(canvas)

        prod_img = _prepare_product(prod_data["image"], sw - 40, sh - 40)

        # Add drop shadow for depth
        prod_img = _add_drop_shadow(prod_img, offset=(5, 5),
                                    blur_radius=10, opacity=50)

        if abs(angle) > 0.5:
            prod_img = prod_img.rotate(angle, resample=Image.BICUBIC,
                                       expand=True)

        img_x = px + (sw - prod_img.width) // 2
        img_y = py + (sh - prod_img.height) // 2
        paste_with_alpha(canvas, prod_img, (img_x, img_y))


# ==============================================================================
# @AmazonHome -- Warm beige/cream with watermark pattern
# ==============================================================================

# Collage: scattered products with rotation, varying sizes, heavy overlap
# Format: (x, y, w, h, rotation_degrees)
_HOME_COLLAGE_POSITIONS = [
    (10, -20, 420, 520, -8),     # top-left, large, tilted left
    (340, 30, 300, 370, 5),      # top-center, medium, slight tilt
    (680, -40, 400, 480, 12),    # top-right, large, tilted right
    (-20, 880, 400, 500, 6),     # bottom-left, large, overlaps title
    (350, 920, 360, 440, -4),    # bottom-center, overlaps heavily
    (700, 860, 380, 500, -10),   # bottom-right, tilted, overlaps
    (500, 400, 240, 300, 15),    # mid-right small accent piece
]

def _home_collage(products, theme_name="Just Dropped"):
    pal = PALETTE["@AmazonHome"]
    bg = hex_to_rgb(pal["bg"])
    wm_color = hex_to_rgb(pal["watermark"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Watermark pattern
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color)

    # Scattered products (some overlap into title area for organic feel)
    _scatter_products(canvas, products, _HOME_COLLAGE_POSITIONS)

    # Title block in center band -- drawn OVER products for layering
    draw = ImageDraw.Draw(canvas)
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 30)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 80)

    ty = 680 + random.randint(-20, 20)
    draw.text((80, ty), _current_month(), font=month_font, fill=accent)
    draw.text((80, ty + 40), theme_name, font=title_font, fill=txt_color)

    return canvas


def _home_individual(product_data, frame_num=1):
    pal = PALETTE["@AmazonHome"]
    bg = hex_to_rgb(pal["bg"])
    wm_color = hex_to_rgb(pal["watermark"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Subtle watermark
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color)

    # Product centered in upper zone
    prod_img = _prepare_product(product_data["image"], 620, 820)
    px = (W - prod_img.width) // 2
    py = 320
    paste_with_alpha(canvas, prod_img, (px, py))

    # Benefit copy + CTA
    copy_y = py + prod_img.height + 50
    _draw_benefit_and_cta(
        canvas, product_data.get("copy", ""),
        product_data.get("product_name", ""),
        txt_color, accent, copy_y,
    )

    return canvas


# ==============================================================================
# @AmazonBeauty -- Mint green with prominent circles
# ==============================================================================

_BEAUTY_COLLAGE_POSITIONS = [
    (20, -10, 480, 560, -6),     # top-left, large, tilted
    (460, 30, 500, 540, 8),      # top-right, large, tilted opposite
    (-10, 920, 500, 580, 5),     # bottom-left, overlaps title heavily
    (450, 960, 520, 560, -7),    # bottom-right, overlaps
    (260, 380, 280, 320, 12),    # center accent, small, rotated
]

def _beauty_collage(products, theme_name="Just Dropped"):
    pal = PALETTE["@AmazonBeauty"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)

    # Scattered products with mint circles -- behind title
    _scatter_products(canvas, products, _BEAUTY_COLLAGE_POSITIONS,
                      circle_color=pal["circle"])

    # Title block in center band -- OVER products
    draw = ImageDraw.Draw(canvas)
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 30)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 78)
    sub_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)

    ty = 660 + random.randint(-20, 20)
    draw.text((80, ty), _current_month(), font=month_font, fill=accent)
    draw.text((80, ty + 40), theme_name, font=title_font, fill=txt_color)
    draw.text((80, ty + 140), "new beauty finds to add to cart",
              font=sub_font, fill=accent)

    return canvas


def _beauty_individual(product_data, frame_num=1):
    pal = PALETTE["@AmazonBeauty"]
    bg = hex_to_rgb(pal["bg_individual"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])
    circle_color = hex_to_rgb(pal["circle"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Large mint circle behind product
    circle_r = 380
    circle_cx, circle_cy = W // 2, 640
    draw.ellipse(
        [circle_cx - circle_r, circle_cy - circle_r,
         circle_cx + circle_r, circle_cy + circle_r],
        fill=circle_color
    )

    # Product on the circle
    prod_img = _prepare_product(product_data["image"], 580, 720)
    px = (W - prod_img.width) // 2
    py = circle_cy - prod_img.height // 2 - 20
    paste_with_alpha(canvas, prod_img, (px, py))

    # Benefit copy + CTA below circle
    copy_y = circle_cy + circle_r + 40
    _draw_benefit_and_cta(
        canvas, product_data.get("copy", ""),
        product_data.get("product_name", ""),
        txt_color, accent, copy_y,
    )

    return canvas


# ==============================================================================
# @AmazonFashion -- Beige/cream, editorial layout
# ==============================================================================

# Fashion collage: editorial scattered with dramatic hero product
_FASHION_COLLAGE_POSITIONS = [
    (480, -30, 600, 720, -5),    # top-right, HERO size, slight tilt
    (-20, 40, 460, 540, 7),      # top-left, medium, tilted
    (280, 300, 300, 360, -12),   # center, small accent, behind title
    (-30, 960, 540, 640, 8),     # bottom-left, large, overlaps title
    (500, 900, 560, 680, -6),    # bottom-right, large, overlaps
    (180, 1200, 280, 340, 14),   # bottom-center accent, rotated
]

def _fashion_collage(products, theme_name="Just Dropped"):
    pal = PALETTE["@AmazonFashion"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)

    # Products BEHIND title -- editorial overlap
    _scatter_products(canvas, products, _FASHION_COLLAGE_POSITIONS)

    # Stacked editorial title OVER products
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 90)
    sub_font = ImageFont.truetype(FONT_TEXT_REGULAR, 22)

    ty = 680 + random.randint(-20, 20)
    draw.text((55, ty), "JUST", font=title_font, fill=txt_color)
    draw.text((55, ty + 100), "DROPPED", font=title_font, fill=txt_color)
    draw.text((60, ty + 210), "DISCOVER MORE MUST-HAVES", font=sub_font, fill=accent)

    # Fashion collage has CTA (per reference)
    _draw_cta_link(canvas, "AMAZON FASHION", accent, ty + 260)

    return canvas


def _fashion_individual(product_data, frame_num=1):
    pal = PALETTE["@AmazonFashion"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Product -- EXTRA LARGE for fashion editorial feel
    prod_img = _prepare_product(product_data["image"], 860, 1100)
    px = (W - prod_img.width) // 2
    py = 200
    paste_with_alpha(canvas, prod_img, (px, py))

    # Benefit copy + CTA below product
    copy_y = py + prod_img.height + 40
    _draw_benefit_and_cta(
        canvas, product_data.get("copy", ""),
        product_data.get("product_name", ""),
        txt_color, accent, copy_y,
    )

    return canvas


# ==============================================================================
# @Amazon (Main) -- Soft pastel gradients + near-invisible watermark
# ==============================================================================

# Collage: scattered products with rotation across pastel gradients
_AMAZON_COLLAGE_POSITIONS = [
    (20, -10, 420, 500, -7),     # top-left, large, tilted
    (380, 20, 380, 460, 6),      # top-center, medium
    (720, -30, 360, 440, 10),    # top-right, tilted right
    (10, 880, 400, 500, 5),      # bottom-left, overlaps title
    (380, 860, 380, 480, -8),    # bottom-center, overlaps heavily
    (720, 900, 360, 460, 7),     # bottom-right
    (520, 360, 260, 300, -14),   # mid-right accent, rotated
]

def _amazon_collage(products, theme_name="Just Dropped", gradient_idx=0):
    pal = PALETTE["@Amazon"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])
    draw = ImageDraw.Draw(canvas)

    # Watermark -- use gradient-matched color (barely visible)
    wm_colors = pal["gradient_watermarks"]
    wm_color = hex_to_rgb(wm_colors[gradient_idx % len(wm_colors)])
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color)

    # Scattered products -- overlap into title zone
    _scatter_products(canvas, products, _AMAZON_COLLAGE_POSITIONS)

    # Title OVER products
    draw = ImageDraw.Draw(canvas)
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 28)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 78)

    ty = 680 + random.randint(-20, 20)
    draw.text((80, ty), _current_month(), font=month_font, fill=accent)
    draw.text((80, ty + 40), theme_name, font=title_font, fill=txt_color)

    return canvas


def _amazon_individual(product_data, frame_num=1, gradient_idx=0):
    pal = PALETTE["@Amazon"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])
    draw = ImageDraw.Draw(canvas)

    # Watermark -- gradient-matched color (barely visible per reference)
    wm_colors = pal["gradient_watermarks"]
    wm_color = hex_to_rgb(wm_colors[gradient_idx % len(wm_colors)])
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color)

    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    # Product centered
    prod_img = _prepare_product(product_data["image"], 620, 820)
    px = (W - prod_img.width) // 2
    py = 320
    paste_with_alpha(canvas, prod_img, (px, py))

    # Benefit copy + CTA
    copy_y = py + prod_img.height + 50
    _draw_benefit_and_cta(
        canvas, product_data.get("copy", ""),
        product_data.get("product_name", ""),
        txt_color, accent, copy_y,
    )

    return canvas


# ==============================================================================
# @Amazon.ca -- Same as @Amazon but with French support
# ==============================================================================

_FR_MONTHS = {
    "january": "janvier", "february": "fevrier", "march": "mars",
    "april": "avril", "may": "mai", "june": "juin", "july": "juillet",
    "august": "aout", "september": "septembre", "october": "octobre",
    "november": "novembre", "december": "decembre",
}

def _ca_collage(products, theme_name="Just Dropped", lang="en", gradient_idx=0):
    pal = PALETTE["@Amazon.ca"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])
    draw = ImageDraw.Draw(canvas)

    # Watermark
    wm_colors = pal["gradient_watermarks"]
    wm_color = hex_to_rgb(wm_colors[gradient_idx % len(wm_colors)])
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color)

    # Scattered products
    _scatter_products(canvas, products, _AMAZON_COLLAGE_POSITIONS)

    # Title
    draw = ImageDraw.Draw(canvas)
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 28)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 78)

    month = _current_month()
    if lang == "fr":
        month = _FR_MONTHS.get(month, month)
    title_text = "Tout juste sorti" if lang == "fr" else theme_name

    ty = 680 + random.randint(-20, 20)
    draw.text((80, ty), month, font=month_font, fill=accent)
    draw.text((80, ty + 40), title_text, font=title_font, fill=txt_color)

    return canvas


def _ca_individual(product_data, frame_num=1, lang="en", gradient_idx=0):
    pal = PALETTE["@Amazon.ca"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])
    draw = ImageDraw.Draw(canvas)

    # Watermark -- gradient-matched
    wm_colors = pal["gradient_watermarks"]
    wm_color = hex_to_rgb(wm_colors[gradient_idx % len(wm_colors)])
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color)

    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    # Product centered
    prod_img = _prepare_product(product_data["image"], 620, 820)
    px = (W - prod_img.width) // 2
    py = 320
    paste_with_alpha(canvas, prod_img, (px, py))

    # Benefit copy + CTA (French CTA for fr)
    copy_y = py + prod_img.height + 50
    draw2 = ImageDraw.Draw(canvas)

    if product_data.get("copy"):
        copy_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)
        copy_h = _draw_text_block(
            draw2, product_data["copy"], 80, copy_y,
            copy_font, txt_color,
            max_width=W - 160, align="center",
            line_spacing=10, max_lines=2,
        )
    else:
        copy_h = 0

    cta_y = copy_y + copy_h + 40
    pname = product_data.get("product_name", "")
    if pname:
        cta_prefix = "MAGASINER" if lang == "fr" else "SHOP"
        cta_font = ImageFont.truetype(FONT_TEXT_BOLD, 22)
        cta_text = f"{cta_prefix} {pname.upper()}"
        cta_bb = draw2.textbbox((0, 0), cta_text, font=cta_font)
        cta_w = cta_bb[2] - cta_bb[0]
        icon_size = 20
        total_w = icon_size + 10 + cta_w
        start_x = (W - total_w) // 2
        cx = start_x + icon_size // 2
        cy = cta_y + icon_size // 2
        draw2.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=accent, width=2)
        draw2.line([(cx - 3, cy + 3), (cx + 4, cy - 4)], fill=accent, width=2)
        draw2.line([(cx + 4, cy - 4), (cx - 1, cy - 4)], fill=accent, width=2)
        draw2.line([(cx + 4, cy - 4), (cx + 4, cy + 1)], fill=accent, width=2)
        draw2.text((start_x + icon_size + 10, cta_y - 2), cta_text,
                   font=cta_font, fill=accent)

    return canvas


# ==============================================================================
# Public API
# ==============================================================================

CHANNEL_BUILDERS = {
    "@AmazonHome": {
        "collage": _home_collage,
        "individual": _home_individual,
    },
    "@AmazonBeauty": {
        "collage": _beauty_collage,
        "individual": _beauty_individual,
    },
    "@AmazonFashion": {
        "collage": _fashion_collage,
        "individual": _fashion_individual,
    },
    "@Amazon": {
        "collage": _amazon_collage,
        "individual": _amazon_individual,
    },
    "@Amazon.ca": {
        "collage": _ca_collage,
        "individual": _ca_individual,
    },
}


def generate_franchise_frames(channel, products, theme_name="Just Dropped"):
    builders = CHANNEL_BUILDERS[channel]
    results = []

    gradient_idx = random.randint(0, 5)
    safe_channel = channel.replace("@", "").replace(".", "_")

    # Frame 1: Collage
    if channel in ("@Amazon", "@Amazon.ca"):
        if channel == "@Amazon.ca":
            collage_en = builders["collage"](products, theme_name, lang="en",
                                             gradient_idx=gradient_idx)
        else:
            collage_en = builders["collage"](products, theme_name,
                                             gradient_idx=gradient_idx)
    else:
        collage_en = builders["collage"](products, theme_name)

    collage_buf = _save_frame(collage_en)
    results.append((f"{safe_channel}/Frame_01_Collage.png", collage_buf))

    # Frames 2 to N+1: Individual product frames
    for i, prod in enumerate(products):
        frame_num = i + 1
        if channel == "@Amazon":
            frame = builders["individual"](prod, frame_num=frame_num,
                                           gradient_idx=(gradient_idx + i) % 6)
        elif channel == "@Amazon.ca":
            frame = builders["individual"](prod, frame_num=frame_num, lang="en",
                                           gradient_idx=(gradient_idx + i) % 6)
        else:
            frame = builders["individual"](prod, frame_num=frame_num)

        buf = _save_frame(frame)
        results.append((
            f"{safe_channel}/Frame_{i+2:02d}_{prod.get('asin', f'Product_{i+1}')}.png",
            buf,
        ))

    # Last frame: Duplicate of Frame 1
    collage_buf_dup = _save_frame(collage_en)
    results.append((
        f"{safe_channel}/Frame_{len(products)+2:02d}_Collage.png",
        collage_buf_dup,
    ))

    # @Amazon.ca: French versions
    if channel == "@Amazon.ca":
        collage_fr = builders["collage"](products, theme_name, lang="fr",
                                         gradient_idx=gradient_idx)
        fr_buf = _save_frame(collage_fr)
        results.append((f"{safe_channel}_FR/Frame_01_Collage.png", fr_buf))

        for i, prod in enumerate(products):
            frame_fr = builders["individual"](prod, frame_num=i+1, lang="fr",
                                              gradient_idx=(gradient_idx + i) % 6)
            buf_fr = _save_frame(frame_fr)
            results.append((
                f"{safe_channel}_FR/Frame_{i+2:02d}_{prod.get('asin', f'Product_{i+1}')}.png",
                buf_fr,
            ))

        collage_fr_dup = _save_frame(collage_fr)
        results.append((
            f"{safe_channel}_FR/Frame_{len(products)+2:02d}_Collage.png",
            collage_fr_dup,
        ))

    return results


def generate_all_franchises(franchise_data, theme_names=None):
    if theme_names is None:
        theme_names = {}

    all_results = []
    for channel, products in franchise_data.items():
        if channel not in CHANNEL_BUILDERS:
            continue
        theme = theme_names.get(channel, "Just Dropped")
        frames = generate_franchise_frames(channel, products, theme)
        all_results.extend(frames)

    return all_results
