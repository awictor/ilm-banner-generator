"""
Instagram Story Frame Generator – engine module

Generates 1080x1920px story frames for 5 Amazon channels:
  @AmazonHome, @AmazonBeauty, @AmazonFashion, @Amazon, @Amazon.ca

Each channel has a distinct visual style with collage and individual layouts.
Frame structure per franchise (10-12 frames):
  Frame 1:    Collage (product selection + "Just Dropped" title)
  Frames 2-N: Individual product frames (1 per ASIN)
  Last frame: Duplicate of Frame 1
"""

import os
from datetime import datetime
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from banner_engine import hex_to_rgb, remove_white_bg, trim_transparent, fit_image, paste_with_alpha

# ── Constants ────────────────────────────────────────────────────
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
        "bg_individual": "#F5F8F6",  # white-ish for individual frames
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


# ── Drawing helpers ──────────────────────────────────────────────

def _make_gradient(w, h, color_top, color_bottom):
    """Create a vertical linear gradient image (vectorized with NumPy)."""
    top = np.array(hex_to_rgb(color_top), dtype=np.float32)
    bot = np.array(hex_to_rgb(color_bottom), dtype=np.float32)
    t = np.linspace(0.0, 1.0, h, dtype=np.float32).reshape(h, 1, 1)
    arr = (top + (bot - top) * t).astype(np.uint8)
    arr = np.broadcast_to(arr, (h, w, 3)).copy()
    return Image.fromarray(arr, "RGB")


def _make_circle_gradient(w, h, center_color, edge_color):
    """Create a radial/circular gradient image (vectorized with NumPy)."""
    center = np.array(hex_to_rgb(center_color), dtype=np.float32)
    edge = np.array(hex_to_rgb(edge_color), dtype=np.float32)
    cx, cy = w / 2.0, h / 2.0
    max_r = np.sqrt(cx ** 2 + cy ** 2)
    ys = np.arange(h, dtype=np.float32) - cy
    xs = np.arange(w, dtype=np.float32) - cx
    dist = np.sqrt(xs[np.newaxis, :] ** 2 + ys[:, np.newaxis] ** 2)
    t = np.clip(dist / max_r, 0.0, 1.0)[:, :, np.newaxis]
    arr = (center + (edge - center) * t).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _draw_text_block(draw, text, x, y, font, color, max_width=None, align="left",
                     line_spacing=8, max_lines=0):
    """Draw text, wrapping if max_width is provided. Returns total height used.

    Args:
        line_spacing: Vertical gap between lines (default 8, preserves old behavior).
        max_lines: Max number of lines to render (0 = unlimited). Last visible
                   line is truncated with "\u2026" if the text overflows.
    """
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

    # Truncate to max_lines with ellipsis on the last visible line
    if max_lines > 0 and len(lines) > max_lines:
        last = lines[max_lines - 1]
        while last:
            candidate = last + "\u2026"
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                break
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        lines = lines[:max_lines - 1] + [last + "\u2026"]

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
    """Draw text in italic to simulate handwritten annotation style."""
    font = ImageFont.truetype(FONT_DISPLAY_ITALIC, size)
    draw.text((x, y), text, font=font, fill=color)
    bb = draw.textbbox((x, y), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]  # width, height


def _draw_watermark_pattern(draw, text, color, font_size=48, spacing_x=320, spacing_y=100):
    """Tile repeated watermark text across the entire canvas at an angle."""
    font = ImageFont.truetype(FONT_DISPLAY_BOLD, font_size)
    # Draw with rotation by rendering on a larger temporary image is complex,
    # so we tile horizontally with slight vertical offset per row for a diagonal feel
    for row in range(-2, H // spacing_y + 2):
        offset_x = (row % 2) * (spacing_x // 2)  # stagger every other row
        for col in range(-1, W // spacing_x + 2):
            tx = col * spacing_x + offset_x
            ty = row * spacing_y
            draw.text((tx, ty), text, font=font, fill=color)


def _prepare_product(product_image, max_w, max_h):
    """Prepare product image: convert, trim, fit."""
    img = product_image.convert("RGBA")
    img = trim_transparent(img)
    img = fit_image(img, max_w, max_h)
    return img


def _save_frame(canvas):
    """Save canvas to BytesIO as PNG."""
    buf = BytesIO()
    canvas.save(buf, "PNG")
    buf.seek(0)
    return buf


def _pad_products(products, count):
    """Repeat products list to fill at least `count` items."""
    if not products:
        return []
    if len(products) >= count:
        return products[:count]
    return (products * ((count // len(products)) + 1))[:count]


# ── New shared layout helpers ────────────────────────────────────

def _draw_benefit_copy(canvas, text, y_start):
    """Render benefit copy on individual frames.

    FONT_TEXT_BOLD 42pt, #3A3A3A, left-aligned x=40, line_spacing=17, max 3 lines.
    """
    if not text:
        return
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT_TEXT_BOLD, 42)
    color = hex_to_rgb("#3A3A3A")
    _draw_text_block(draw, text, 40, y_start, font, color,
                     max_width=W - 80, align="left",
                     line_spacing=17, max_lines=3)


def _draw_collage_grid(canvas, products, grid_origin_x, grid_origin_y,
                       cols, rows, cell_w=None, cell_h=None,
                       gap_x=20, gap_y=20, circle_color=None):
    """Organized product grid replacing random scattering.

    Lays out products in a *cols* x *rows* grid starting at
    (grid_origin_x, grid_origin_y).  Optional *circle_color* (hex)
    draws a circle behind each product (Beauty channel motif).
    """
    if cell_w is None:
        cell_w = (W - 2 * grid_origin_x - (cols - 1) * gap_x) // cols
    if cell_h is None:
        cell_h = (H - grid_origin_y - 60 - (rows - 1) * gap_y) // rows

    draw = ImageDraw.Draw(canvas)
    display = _pad_products(products, cols * rows)

    for idx, prod_data in enumerate(display):
        col = idx % cols
        row = idx // cols
        if row >= rows:
            break
        cx = grid_origin_x + col * (cell_w + gap_x)
        cy = grid_origin_y + row * (cell_h + gap_y)

        if circle_color:
            cr = min(cell_w, cell_h) // 2 - 10
            ccx = cx + cell_w // 2
            ccy = cy + cell_h // 2
            draw.ellipse([ccx - cr, ccy - cr, ccx + cr, ccy + cr],
                         fill=hex_to_rgb(circle_color))

        prod_img = _prepare_product(prod_data["image"],
                                    cell_w - 40, cell_h - 40)
        img_x = cx + (cell_w - prod_img.width) // 2
        img_y = cy + (cell_h - prod_img.height) // 2
        paste_with_alpha(canvas, prod_img, (img_x, img_y))


def _draw_collage_header(canvas, theme_name, month_text, text_color, accent_color):
    """Month label italic + theme title bold, left-aligned x=60."""
    draw = ImageDraw.Draw(canvas)
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 30)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 80)

    draw.text((60, 80), f"{month_text}.", font=month_font,
              fill=hex_to_rgb(accent_color))
    draw.text((60, 120), theme_name, font=title_font,
              fill=hex_to_rgb(text_color))


# ══════════════════════════════════════════════════════════════════
# @AmazonHome – Warm beige/cream with watermark pattern
# ══════════════════════════════════════════════════════════════════

def _home_collage(products, theme_name="Just Dropped"):
    """
    @AmazonHome collage frame.
    Subtle watermark pattern, campaign header, organized 2x2 product grid.
    """
    pal = PALETTE["@AmazonHome"]
    bg = hex_to_rgb(pal["bg"])
    wm_color = hex_to_rgb(pal["watermark"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Subtle watermark pattern (collage only)
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color, font_size=42,
                            spacing_x=360, spacing_y=90)

    # Campaign branding header
    _draw_collage_header(canvas, theme_name, _current_month(),
                         pal["text"], pal["accent"])

    # Organized 2x2 product grid
    _draw_collage_grid(canvas, products,
                       grid_origin_x=60, grid_origin_y=260,
                       cols=2, rows=2, gap_x=30, gap_y=30)

    return canvas


def _home_individual(product_data, frame_num=1):
    """
    @AmazonHome individual frame.
    Clean #E8E6E0 bg, product in top 60%, benefit copy in bottom 40%.
    No watermark, no handwritten annotations.
    """
    pal = PALETTE["@AmazonHome"]
    bg = hex_to_rgb(pal["bg"])

    canvas = Image.new("RGB", (W, H), bg)

    # Top 60 %: product zone (y=0..1152)
    prod_img = _prepare_product(product_data["image"], 600, 900)
    px = (W - prod_img.width) // 2
    py = (1152 - prod_img.height) // 2
    paste_with_alpha(canvas, prod_img, (px, py))

    # Bottom 40 %: copy zone (y=1152+)
    _draw_benefit_copy(canvas, product_data.get("copy", ""), y_start=1192)

    return canvas


# ══════════════════════════════════════════════════════════════════
# @AmazonBeauty – Mint green with prominent circles
# ══════════════════════════════════════════════════════════════════

def _beauty_collage(products, theme_name="Just Dropped"):
    """
    @AmazonBeauty collage frame.
    Mint bg, campaign header, subtitle, organized 2x2 grid with mint circles.
    """
    pal = PALETTE["@AmazonBeauty"]
    bg = hex_to_rgb(pal["bg"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Campaign branding header
    _draw_collage_header(canvas, theme_name, _current_month(),
                         pal["text"], pal["accent"])

    # Subtitle below header
    sub_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)
    draw.text((60, 220), "new beauty finds to add to cart",
              font=sub_font, fill=accent)

    # Organized 2x2 grid with mint circle motif
    _draw_collage_grid(canvas, products,
                       grid_origin_x=60, grid_origin_y=300,
                       cols=2, rows=2, gap_x=30, gap_y=30,
                       circle_color=pal["circle"])

    return canvas


def _beauty_individual(product_data, frame_num=1):
    """
    @AmazonBeauty individual frame.
    Light bg, mint circle repositioned to top zone (cy=576),
    product in top 60%, benefit copy in bottom 40%.
    No handwritten annotations.
    """
    pal = PALETTE["@AmazonBeauty"]
    bg = hex_to_rgb(pal["bg_individual"])
    circle_color = hex_to_rgb(pal["circle"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Mint circle – centered in top zone
    circle_r = 380
    circle_cx, circle_cy = W // 2, 576
    draw.ellipse(
        [circle_cx - circle_r, circle_cy - circle_r,
         circle_cx + circle_r, circle_cy + circle_r],
        fill=circle_color
    )

    # Top 60 %: product zone (y=0..1152)
    prod_img = _prepare_product(product_data["image"], 600, 900)
    px = (W - prod_img.width) // 2
    py = (1152 - prod_img.height) // 2
    paste_with_alpha(canvas, prod_img, (px, py))

    # Bottom 40 %: copy zone (y=1152+)
    _draw_benefit_copy(canvas, product_data.get("copy", ""), y_start=1192)

    return canvas


# ══════════════════════════════════════════════════════════════════
# @AmazonFashion – Beige/cream, editorial layout
# ══════════════════════════════════════════════════════════════════

def _fashion_collage(products, theme_name="Just Dropped"):
    """
    @AmazonFashion collage frame.
    Stacked "JUST/DROPPED" editorial title, subtitle, organized 2x2 grid.
    """
    pal = PALETTE["@AmazonFashion"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Stacked editorial title
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 90)
    sub_font = ImageFont.truetype(FONT_TEXT_REGULAR, 22)

    draw.text((55, 70), "JUST", font=title_font, fill=txt_color)
    draw.text((55, 170), "DROPPED", font=title_font, fill=txt_color)
    draw.text((60, 280), "DISCOVER MORE MUST-HAVES", font=sub_font, fill=accent)

    # Organized 2x2 product grid below title
    _draw_collage_grid(canvas, products,
                       grid_origin_x=60, grid_origin_y=360,
                       cols=2, rows=2, gap_x=30, gap_y=30)

    return canvas


def _fashion_individual(product_data, frame_num=1):
    """
    @AmazonFashion individual frame.
    Slightly larger product (650x950) for editorial feel,
    product in top 60%, benefit copy in bottom 40%.
    No handwritten annotations.
    """
    pal = PALETTE["@AmazonFashion"]
    bg = hex_to_rgb(pal["bg"])

    canvas = Image.new("RGB", (W, H), bg)

    # Top 60 %: product zone – slightly larger for editorial feel
    prod_img = _prepare_product(product_data["image"], 650, 950)
    px = (W - prod_img.width) // 2
    py = (1152 - prod_img.height) // 2
    paste_with_alpha(canvas, prod_img, (px, py))

    # Bottom 40 %: copy zone (y=1152+)
    _draw_benefit_copy(canvas, product_data.get("copy", ""), y_start=1192)

    return canvas


# ══════════════════════════════════════════════════════════════════
# @Amazon (Main) – Soft pastel gradients
# ══════════════════════════════════════════════════════════════════

def _amazon_collage(products, theme_name="Just Dropped", gradient_idx=0):
    """
    @Amazon collage frame.
    Pastel gradient bg, campaign header, organized 2x2 grid.
    """
    pal = PALETTE["@Amazon"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])

    # Campaign branding header
    _draw_collage_header(canvas, theme_name, _current_month(),
                         pal["text"], pal["accent"])

    # Organized 2x2 product grid
    _draw_collage_grid(canvas, products,
                       grid_origin_x=60, grid_origin_y=260,
                       cols=2, rows=2, gap_x=30, gap_y=30)

    return canvas


def _amazon_individual(product_data, frame_num=1, gradient_idx=0):
    """
    @Amazon individual frame.
    Cycling pastel gradients, product in top 60%, benefit copy in bottom 40%.
    No handwritten annotations.
    """
    pal = PALETTE["@Amazon"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])

    # Top 60 %: product zone (y=0..1152)
    prod_img = _prepare_product(product_data["image"], 600, 900)
    px = (W - prod_img.width) // 2
    py = (1152 - prod_img.height) // 2
    paste_with_alpha(canvas, prod_img, (px, py))

    # Bottom 40 %: copy zone (y=1152+)
    _draw_benefit_copy(canvas, product_data.get("copy", ""), y_start=1192)

    return canvas


# ══════════════════════════════════════════════════════════════════
# @Amazon.ca – Same as @Amazon but with Canadian spelling + French
# ══════════════════════════════════════════════════════════════════

def _ca_collage(products, theme_name="Just Dropped", lang="en", gradient_idx=0):
    """@Amazon.ca collage: gradient bg, campaign header, organized grid.
    Supports French title and month label."""
    pal = PALETTE["@Amazon.ca"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])

    # Resolve month (French when needed)
    month = _current_month()
    fr_months = {
        "january": "janvier", "february": "f\u00e9vrier", "march": "mars",
        "april": "avril", "may": "mai", "june": "juin", "july": "juillet",
        "august": "ao\u00fbt", "september": "septembre", "october": "octobre",
        "november": "novembre", "december": "d\u00e9cembre",
    }
    if lang == "fr":
        month = fr_months.get(month, month)

    title_text = "Tout juste sorti" if lang == "fr" else theme_name

    # Campaign branding header
    _draw_collage_header(canvas, title_text, month,
                         pal["text"], pal["accent"])

    # Organized 2x2 product grid
    _draw_collage_grid(canvas, products,
                       grid_origin_x=60, grid_origin_y=260,
                       cols=2, rows=2, gap_x=30, gap_y=30)

    return canvas


def _ca_individual(product_data, frame_num=1, lang="en", gradient_idx=0):
    """@Amazon.ca individual: gradient bg, product top 60%, copy bottom 40%.
    Supports French via lang param."""
    pal = PALETTE["@Amazon.ca"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])

    # Top 60 %: product zone (y=0..1152)
    prod_img = _prepare_product(product_data["image"], 600, 900)
    px = (W - prod_img.width) // 2
    py = (1152 - prod_img.height) // 2
    paste_with_alpha(canvas, prod_img, (px, py))

    # Bottom 40 %: copy zone (y=1152+)
    _draw_benefit_copy(canvas, product_data.get("copy", ""), y_start=1192)

    return canvas


# ══════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════

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
    """
    Generate all frames for a single franchise/channel.

    Args:
        channel: One of the 5 channel names (e.g. "@AmazonHome")
        products: List of dicts with keys: image (PIL Image), asin, brand,
                  product_name, copy
        theme_name: Theme name for the title card

    Returns:
        List of (filename, BytesIO) tuples.
        Frame 1: collage, Frames 2-N+1: individual, Last frame: collage duplicate.
    """
    builders = CHANNEL_BUILDERS[channel]
    results = []

    gradient_idx = 0
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

    # For @Amazon.ca, also generate French versions
    if channel == "@Amazon.ca":
        fr_theme = theme_name
        collage_fr = builders["collage"](products, fr_theme, lang="fr",
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
    """
    Generate frames for all franchises.

    Args:
        franchise_data: dict {channel_name: [product_dicts]}
        theme_names: dict {channel_name: theme_name} or None

    Returns:
        List of (filename, BytesIO) tuples for all channels.
    """
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
