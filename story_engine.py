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
        "bg": "#F5F1ED",
        "text": "#2C2C2C",
        "accent": "#8B7D6B",
        "watermark": "#EDE9E3",
    },
    "@AmazonBeauty": {
        "bg": "#D4EFE0",
        "bg_individual": "#F5F8F6",  # white-ish for individual frames
        "circle": "#C8EDDA",
        "text": "#2C2C2C",
        "accent": "#4A8B6F",
    },
    "@AmazonFashion": {
        "bg": "#F0EBE6",
        "text": "#2C2C2C",
        "accent": "#8B7D6B",
    },
    "@Amazon": {
        "bg": "#F5E6DC",
        "text": "#2C2C2C",
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
        "text": "#2C2C2C",
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


def _draw_text_block(draw, text, x, y, font, color, max_width=None, align="left"):
    """Draw text, wrapping if max_width is provided. Returns total height used."""
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
        total_h += (line_bb[3] - line_bb[1]) + 8
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


# ══════════════════════════════════════════════════════════════════
# @AmazonHome – Warm beige/cream with watermark pattern
# ══════════════════════════════════════════════════════════════════

def _home_collage(products, theme_name="Just Dropped"):
    """
    @AmazonHome collage frame.
    Reference: warm beige bg, "JUST DROPPED" watermark pattern, month label
    in small italic, "Just Dropped" in large bold left-aligned, products
    scattered across frame.
    """
    pal = PALETTE["@AmazonHome"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])
    wm_color = hex_to_rgb(pal["watermark"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Watermark pattern
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color, font_size=42,
                            spacing_x=360, spacing_y=90)

    # Month label (small italic)
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 30)
    draw.text((80, 730), _current_month(), font=month_font, fill=accent)

    # "Just Dropped" title
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 80)
    draw.text((80, 770), "Just Dropped", font=title_font, fill=txt_color)

    # Products scattered around the title
    positions = [
        (60, 80, 350, 420),      # top-left
        (430, 50, 320, 380),     # top-center
        (760, 100, 280, 340),    # top-right
        (60, 960, 330, 400),     # bottom-left
        (420, 920, 320, 400),    # bottom-center
        (740, 980, 300, 380),    # bottom-right
    ]

    display = _pad_products(products, len(positions))
    for idx, prod_data in enumerate(display):
        px, py, pw, ph = positions[idx]
        prod_img = _prepare_product(prod_data["image"], pw - 30, ph - 30)
        img_x = px + (pw - prod_img.width) // 2
        img_y = py + (ph - prod_img.height) // 2
        paste_with_alpha(canvas, prod_img, (img_x, img_y))

        # Handwritten annotation near product
        if prod_data.get("copy"):
            note = prod_data["copy"][:25]
            _draw_handwritten(draw, note, px + 10, py - 5, accent, size=20)

    return canvas


def _home_individual(product_data, frame_num=1):
    """
    @AmazonHome individual frame.
    Reference: warm beige bg with watermark, product centered vertically,
    handwritten annotation above product, benefit copy below center-aligned.
    """
    pal = PALETTE["@AmazonHome"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])
    wm_color = hex_to_rgb(pal["watermark"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Watermark pattern
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color, font_size=42,
                            spacing_x=360, spacing_y=90)

    # Handwritten annotation – above product area
    if product_data.get("copy"):
        annotation = product_data["copy"][:35]
        aw, _ = _draw_handwritten(draw, annotation, 0, 0, accent, size=26)
        # Center the annotation horizontally
        ax = (W - aw) // 2
        _draw_handwritten(draw, annotation, ax, 340, accent, size=26)

    # Product image – centered
    prod_img = _prepare_product(product_data["image"], 650, 800)
    px = (W - prod_img.width) // 2
    py = 420
    paste_with_alpha(canvas, prod_img, (px, py))

    # Benefit copy – below product, center-aligned
    copy_font = ImageFont.truetype(FONT_TEXT_REGULAR, 30)

    copy_y = py + prod_img.height + 60
    if product_data.get("copy"):
        _draw_text_block(
            draw, product_data["copy"], 80, copy_y,
            copy_font, txt_color, max_width=W - 160, align="center"
        )

    return canvas


# ══════════════════════════════════════════════════════════════════
# @AmazonBeauty – Mint green with prominent circles
# ══════════════════════════════════════════════════════════════════

def _beauty_collage(products, theme_name="Just Dropped"):
    """
    @AmazonBeauty collage frame.
    Reference: mint green bg, "Just Dropped" bold + subtitle centered,
    month label, products with mint circles behind them.
    """
    pal = PALETTE["@AmazonBeauty"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])
    circle_color = hex_to_rgb(pal["circle"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Month label
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 28)
    draw.text((80, 680), _current_month(), font=month_font, fill=accent)

    # "Just Dropped" – left-aligned bold
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 78)
    draw.text((80, 720), "Just Dropped", font=title_font, fill=txt_color)

    # Subtitle
    sub_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)
    draw.text((80, 815), "new beauty finds to add to cart",
              font=sub_font, fill=accent)

    # Products scattered with mint circles
    positions = [
        (80, 60, 400, 480),      # top-left
        (520, 30, 380, 460),     # top-right
        (60, 930, 420, 500),     # bottom-left
        (500, 960, 400, 480),    # bottom-right
    ]

    display = _pad_products(products, len(positions))
    for idx, prod_data in enumerate(display):
        px, py, pw, ph = positions[idx]
        # Mint circle behind product
        cr = min(pw, ph) // 2 - 10
        ccx = px + pw // 2
        ccy = py + ph // 2
        draw.ellipse([ccx - cr, ccy - cr, ccx + cr, ccy + cr], fill=circle_color)

        prod_img = _prepare_product(prod_data["image"], pw - 80, ph - 80)
        img_x = px + (pw - prod_img.width) // 2
        img_y = py + (ph - prod_img.height) // 2
        paste_with_alpha(canvas, prod_img, (img_x, img_y))

    return canvas


def _beauty_individual(product_data, frame_num=1):
    """
    @AmazonBeauty individual frame.
    Reference: white/light bg, large mint circle in center area,
    product sitting on circle, handwritten annotation above,
    benefit copy below center-aligned.
    """
    pal = PALETTE["@AmazonBeauty"]
    bg = hex_to_rgb(pal["bg_individual"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])
    circle_color = hex_to_rgb(pal["circle"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Large mint circle – positioned in center-lower area
    circle_r = 380
    circle_cx, circle_cy = W // 2, 820
    draw.ellipse(
        [circle_cx - circle_r, circle_cy - circle_r,
         circle_cx + circle_r, circle_cy + circle_r],
        fill=circle_color
    )

    # Product on the circle
    prod_img = _prepare_product(product_data["image"], 580, 700)
    px = (W - prod_img.width) // 2
    py = circle_cy - prod_img.height // 2 - 40
    paste_with_alpha(canvas, prod_img, (px, py))

    # Handwritten annotation above product
    if product_data.get("copy"):
        annotation = product_data["copy"][:30]
        aw, _ = _draw_handwritten(draw, annotation, 0, 0, accent, size=24)
        ax = (W - aw) // 2
        _draw_handwritten(draw, annotation, ax, py - 50, accent, size=24)

    # Benefit copy – below circle, center-aligned
    copy_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)
    copy_y = circle_cy + circle_r + 50

    if product_data.get("copy"):
        _draw_text_block(
            draw, product_data["copy"], 80, copy_y,
            copy_font, txt_color, max_width=W - 160, align="center"
        )

    return canvas


# ══════════════════════════════════════════════════════════════════
# @AmazonFashion – Beige/cream, editorial layout
# ══════════════════════════════════════════════════════════════════

def _fashion_collage(products, theme_name="Just Dropped"):
    """
    @AmazonFashion collage frame.
    Reference: beige bg, "JUST" / "DROPPED" stacked in large bold caps,
    "DISCOVER MORE MUST-HAVES" subtitle, products scattered editorially.
    """
    pal = PALETTE["@AmazonFashion"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Products first (behind text) – editorial scattered
    positions = [
        (500, 40, 500, 600),     # top-right, large
        (40, 50, 400, 480),      # top-left
        (60, 1050, 460, 560),    # bottom-left
        (540, 1000, 480, 580),   # bottom-right
        (320, 540, 380, 460),    # center
    ]

    display = _pad_products(products, len(positions))
    for idx, prod_data in enumerate(display):
        px, py, pw, ph = positions[idx]
        prod_img = _prepare_product(prod_data["image"], pw - 30, ph - 30)
        img_x = px + (pw - prod_img.width) // 2
        img_y = py + (ph - prod_img.height) // 2
        paste_with_alpha(canvas, prod_img, (img_x, img_y))

    # Draw title over products
    draw = ImageDraw.Draw(canvas)  # refresh after pastes
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 90)
    sub_font = ImageFont.truetype(FONT_TEXT_REGULAR, 22)

    # Stacked "JUST" / "DROPPED" – left side, vertically centered
    draw.text((55, 680), "JUST", font=title_font, fill=txt_color)
    draw.text((55, 780), "DROPPED", font=title_font, fill=txt_color)

    # Subtitle
    draw.text((60, 890), "DISCOVER MORE MUST-HAVES", font=sub_font, fill=accent)

    return canvas


def _fashion_individual(product_data, frame_num=1):
    """
    @AmazonFashion individual frame.
    Reference: beige bg, product takes up large area of frame, handwritten
    annotations scattered around product, benefit copy below.
    """
    pal = PALETTE["@AmazonFashion"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Product image – large, centered
    prod_img = _prepare_product(product_data["image"], 800, 1100)
    px = (W - prod_img.width) // 2
    py = 250
    paste_with_alpha(canvas, prod_img, (px, py))

    # Handwritten annotations scattered around product
    if product_data.get("copy"):
        words = product_data["copy"].split()
        chunks = []
        if len(words) > 4:
            chunks.append(" ".join(words[:3]))
            chunks.append(" ".join(words[3:6]))
        else:
            chunks.append(product_data["copy"][:30])

        scatter_positions = [
            (px + prod_img.width - 40, py - 30),
            (px - 20, py + prod_img.height // 3),
        ]
        for i, chunk in enumerate(chunks[:2]):
            sx, sy = scatter_positions[i % len(scatter_positions)]
            sx = max(20, min(sx, W - 250))
            sy = max(20, min(sy, H - 60))
            _draw_handwritten(draw, chunk, sx, sy, accent, size=22)

    # Benefit copy – below product, center-aligned
    copy_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)
    copy_y = py + prod_img.height + 50

    if product_data.get("copy"):
        _draw_text_block(
            draw, product_data["copy"], 80, copy_y,
            copy_font, txt_color, max_width=W - 160, align="center"
        )

    return canvas


# ══════════════════════════════════════════════════════════════════
# @Amazon (Main) – Soft pastel gradients
# ══════════════════════════════════════════════════════════════════

def _amazon_collage(products, theme_name="Just Dropped", gradient_idx=0):
    """
    @Amazon collage frame.
    Reference: soft pastel gradient bg, month label, "Just Dropped" left-aligned,
    products scattered artistically.
    """
    pal = PALETTE["@Amazon"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])
    draw = ImageDraw.Draw(canvas)

    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    # Month label
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 28)
    draw.text((80, 700), _current_month(), font=month_font, fill=accent)

    # "Just Dropped" title
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 78)
    draw.text((80, 740), "Just Dropped", font=title_font, fill=txt_color)

    # Products scattered
    positions = [
        (60, 60, 380, 460),      # top-left
        (480, 40, 360, 440),     # top-center
        (760, 80, 280, 360),     # top-right
        (60, 940, 360, 440),     # bottom-left
        (460, 920, 340, 420),    # bottom-center
        (740, 960, 300, 380),    # bottom-right
    ]

    display = _pad_products(products, len(positions))
    for idx, prod_data in enumerate(display):
        px, py, pw, ph = positions[idx]
        prod_img = _prepare_product(prod_data["image"], pw - 30, ph - 30)
        img_x = px + (pw - prod_img.width) // 2
        img_y = py + (ph - prod_img.height) // 2
        paste_with_alpha(canvas, prod_img, (img_x, img_y))

    return canvas


def _amazon_individual(product_data, frame_num=1, gradient_idx=0):
    """
    @Amazon individual frame.
    Reference: each frame uses a different pastel gradient, product centered,
    handwritten annotation above product, benefit copy below center-aligned.
    """
    pal = PALETTE["@Amazon"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])
    draw = ImageDraw.Draw(canvas)

    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    # Handwritten annotation above product
    if product_data.get("copy"):
        annotation = product_data["copy"][:30]
        aw, _ = _draw_handwritten(draw, annotation, 0, 0, accent, size=26)
        ax = (W - aw) // 2
        _draw_handwritten(draw, annotation, ax, 340, accent, size=26)

    # Product – centered
    prod_img = _prepare_product(product_data["image"], 680, 820)
    px = (W - prod_img.width) // 2
    py = 420
    paste_with_alpha(canvas, prod_img, (px, py))

    # Benefit copy – below product, center-aligned
    copy_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)
    copy_y = py + prod_img.height + 60

    if product_data.get("copy"):
        _draw_text_block(
            draw, product_data["copy"], 80, copy_y,
            copy_font, txt_color, max_width=W - 160, align="center"
        )

    return canvas


# ══════════════════════════════════════════════════════════════════
# @Amazon.ca – Same as @Amazon but with Canadian spelling + French
# ══════════════════════════════════════════════════════════════════

def _ca_collage(products, theme_name="Just Dropped", lang="en", gradient_idx=0):
    """@Amazon.ca collage: same layout as @Amazon, supports French title."""
    pal = PALETTE["@Amazon.ca"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])
    draw = ImageDraw.Draw(canvas)

    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    # Month label
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 28)
    month = _current_month()
    # French month names
    fr_months = {
        "january": "janvier", "february": "f\u00e9vrier", "march": "mars",
        "april": "avril", "may": "mai", "june": "juin", "july": "juillet",
        "august": "ao\u00fbt", "september": "septembre", "october": "octobre",
        "november": "novembre", "december": "d\u00e9cembre",
    }
    if lang == "fr":
        month = fr_months.get(month, month)
    draw.text((80, 700), month, font=month_font, fill=accent)

    # Title
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 78)
    title_text = "Tout juste sorti" if lang == "fr" else "Just Dropped"
    draw.text((80, 740), title_text, font=title_font, fill=txt_color)

    # Products scattered
    positions = [
        (60, 60, 380, 460),
        (480, 40, 360, 440),
        (760, 80, 280, 360),
        (60, 940, 360, 440),
        (460, 920, 340, 420),
        (740, 960, 300, 380),
    ]

    display = _pad_products(products, len(positions))
    for idx, prod_data in enumerate(display):
        px, py, pw, ph = positions[idx]
        prod_img = _prepare_product(prod_data["image"], pw - 30, ph - 30)
        img_x = px + (pw - prod_img.width) // 2
        img_y = py + (ph - prod_img.height) // 2
        paste_with_alpha(canvas, prod_img, (img_x, img_y))

    return canvas


def _ca_individual(product_data, frame_num=1, lang="en", gradient_idx=0):
    """@Amazon.ca individual: same layout as @Amazon, supports French."""
    pal = PALETTE["@Amazon.ca"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])
    draw = ImageDraw.Draw(canvas)

    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    # Handwritten annotation above product
    if product_data.get("copy"):
        annotation = product_data["copy"][:30]
        aw, _ = _draw_handwritten(draw, annotation, 0, 0, accent, size=26)
        ax = (W - aw) // 2
        _draw_handwritten(draw, annotation, ax, 340, accent, size=26)

    # Product – centered
    prod_img = _prepare_product(product_data["image"], 680, 820)
    px = (W - prod_img.width) // 2
    py = 420
    paste_with_alpha(canvas, prod_img, (px, py))

    # Benefit copy – below product, center-aligned
    copy_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)
    copy_y = py + prod_img.height + 60

    if product_data.get("copy"):
        _draw_text_block(
            draw, product_data["copy"], 80, copy_y,
            copy_font, txt_color, max_width=W - 160, align="center"
        )

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
