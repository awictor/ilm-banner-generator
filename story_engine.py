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
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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


def _add_white_outline(img, thickness=4):
    """Add a white 'sticker cutout' outline around product silhouette."""
    img = img.convert("RGBA")
    pad = thickness * 2
    new_w = img.width + pad * 2
    new_h = img.height + pad * 2
    result = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))

    # Dilate the alpha channel to create expanded silhouette
    alpha = img.split()[3]
    # Pad alpha into larger canvas
    alpha_padded = Image.new("L", (new_w, new_h), 0)
    alpha_padded.paste(alpha, (pad, pad))
    # MaxFilter with kernel size = 2*thickness+1 dilates the alpha
    kernel_size = 2 * thickness + 1
    dilated = alpha_padded.filter(ImageFilter.MaxFilter(kernel_size))

    # Create white silhouette using dilated alpha
    white_layer = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
    white_layer.putalpha(dilated)

    # Composite: white outline first, then original on top
    result = Image.alpha_composite(result, white_layer)
    result.paste(img, (pad, pad), img)
    return result


def _add_colored_glow(img, color="#000000", radius=20, opacity=80):
    """Add a soft colored halo/glow behind the product."""
    img = img.convert("RGBA")
    rgb = hex_to_rgb(color) if isinstance(color, str) else color
    pad = radius * 3
    new_w = img.width + pad * 2
    new_h = img.height + pad * 2
    result = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))

    # Create colored silhouette from alpha
    alpha = img.split()[3]
    alpha_padded = Image.new("L", (new_w, new_h), 0)
    alpha_padded.paste(alpha, (pad, pad))

    glow_layer = Image.new("RGBA", (new_w, new_h), (*rgb, 0))
    # Scale alpha for opacity
    alpha_scaled = alpha_padded.point(lambda p: min(p, opacity))
    glow_layer.putalpha(alpha_scaled)

    # Blur the glow
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=radius))

    # Composite: glow first, then original on top
    result = Image.alpha_composite(result, glow_layer)
    result.paste(img, (pad, pad), img)
    return result


def _add_sparkles(img, count=5, seed=None):
    """Draw small 4-point star sparkles near the product edges."""
    img = img.convert("RGBA")
    rng = random.Random(seed)

    result = img.copy()
    draw = ImageDraw.Draw(result)

    # Find product bounding box from alpha
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    if not bbox:
        return result

    x0, y0, x1, y1 = bbox
    margin = 30  # sparkles near edges, slightly outside

    for _ in range(count):
        # Place sparkles near edges
        side = rng.choice(["top", "bottom", "left", "right"])
        if side == "top":
            sx = rng.randint(x0 - margin, x1 + margin)
            sy = rng.randint(max(0, y0 - margin * 2), y0 + margin)
        elif side == "bottom":
            sx = rng.randint(x0 - margin, x1 + margin)
            sy = rng.randint(y1 - margin, min(img.height - 1, y1 + margin * 2))
        elif side == "left":
            sx = rng.randint(max(0, x0 - margin * 2), x0 + margin)
            sy = rng.randint(y0 - margin, y1 + margin)
        else:
            sx = rng.randint(x1 - margin, min(img.width - 1, x1 + margin * 2))
            sy = rng.randint(y0 - margin, y1 + margin)

        # Clamp to image bounds
        sx = max(2, min(img.width - 3, sx))
        sy = max(2, min(img.height - 3, sy))

        size = rng.randint(6, 14)
        spark_opacity = rng.randint(160, 255)
        color = (255, 255, 255, spark_opacity)

        # Draw 4-point star
        half = size // 2
        # Vertical line
        draw.line([(sx, sy - half), (sx, sy + half)], fill=color, width=2)
        # Horizontal line
        draw.line([(sx - half, sy), (sx + half, sy)], fill=color, width=2)
        # Small diagonal accents
        d = half // 2
        draw.line([(sx - d, sy - d), (sx + d, sy + d)], fill=color, width=1)
        draw.line([(sx + d, sy - d), (sx - d, sy + d)], fill=color, width=1)

    return result


def _add_reflection(img, opacity=40, height_frac=0.3):
    """Add a fading vertical reflection below the product."""
    img = img.convert("RGBA")
    refl_h = int(img.height * height_frac)
    if refl_h < 10:
        return img

    # Crop bottom portion and flip
    bottom_strip = img.crop((0, img.height - refl_h, img.width, img.height))
    reflected = bottom_strip.transpose(Image.FLIP_TOP_BOTTOM)

    # Create gradient alpha fade (full at top -> zero at bottom)
    grad = Image.new("L", (reflected.width, reflected.height), 0)
    for y in range(reflected.height):
        alpha_val = int(opacity * (1.0 - y / reflected.height))
        for x in range(reflected.width):
            grad.putpixel((x, y), alpha_val)

    # Multiply reflected alpha with gradient
    r, g, b, a = reflected.split()
    # Combine: min of existing alpha and gradient
    a_arr = np.minimum(np.array(a), np.array(grad)).astype(np.uint8)
    reflected.putalpha(Image.fromarray(a_arr))

    # Create expanded canvas with gap
    gap = 6
    new_h = img.height + gap + reflected.height
    result = Image.new("RGBA", (img.width, new_h), (0, 0, 0, 0))
    result.paste(img, (0, 0), img)
    result.paste(reflected, (0, img.height + gap), reflected)

    return result


def _add_tilt(img, max_angle=3.0):
    """Apply a small random rotation for a casual editorial feel."""
    angle = random.uniform(-max_angle, max_angle)
    if abs(angle) < 0.3:
        angle = max_angle if random.random() > 0.5 else -max_angle
    return img.rotate(angle, resample=Image.BICUBIC, expand=True,
                      fillcolor=(0, 0, 0, 0))


def _add_float_shadow(img, blur_radius=18, opacity=45, gap=20):
    """Add a separated shadow below the product for a levitation effect."""
    img = img.convert("RGBA")
    alpha = img.split()[3]

    # Shadow canvas with room below
    pad = blur_radius * 2
    new_w = img.width + pad * 2
    new_h = img.height + gap + blur_radius * 3 + pad
    result = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))

    # Create a squashed shadow silhouette (compress vertically for floor shadow)
    squash = 0.15
    shadow_h = max(10, int(img.height * squash))
    alpha_squashed = alpha.resize((img.width, shadow_h), Image.LANCZOS)
    shadow_layer = Image.new("RGBA", (img.width, shadow_h), (0, 0, 0, opacity))
    shadow_layer.putalpha(alpha_squashed)

    # Place shadow below product
    sx = pad
    sy = pad + img.height + gap
    result.paste(shadow_layer, (sx, sy), shadow_layer)
    result = result.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Paste original on top (sharp)
    result.paste(img, (pad, pad), img)
    return result


def _add_polaroid_frame(img, border=16, bottom_extra=40, radius=12):
    """Add a white polaroid/card frame behind the product with rounded corners."""
    img = img.convert("RGBA")
    bbox = img.split()[3].getbbox()
    if not bbox:
        return img

    x0, y0, x1, y1 = bbox
    # Frame rectangle around the product bounding box
    frame_x0 = x0 - border
    frame_y0 = y0 - border
    frame_x1 = x1 + border
    frame_y1 = y1 + border + bottom_extra

    new_w = img.width + border * 2
    new_h = img.height + border + bottom_extra
    result = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))

    # Draw white rounded rectangle
    frame_draw = ImageDraw.Draw(result)
    fx0 = frame_x0 + border
    fy0 = frame_y0 + border
    fx1 = frame_x1 + border
    fy1 = frame_y1 + border
    # Clamp to canvas
    fx0 = max(0, fx0)
    fy0 = max(0, fy0)
    fx1 = min(new_w, fx1)
    fy1 = min(new_h, fy1)
    frame_draw.rounded_rectangle([fx0, fy0, fx1, fy1], radius=radius,
                                  fill=(255, 255, 255, 240))

    # Paste product on top
    result.paste(img, (border, border), img)
    return result


def _add_noise_grain(img, intensity=25):
    """Add subtle film grain/noise texture over the product."""
    img = img.convert("RGBA")
    result = img.copy()

    # Generate noise array matching image size
    noise = np.random.normal(0, intensity, (img.height, img.width)).astype(np.int16)

    # Apply noise to RGB channels only where alpha > 0
    arr = np.array(result)
    alpha_mask = arr[:, :, 3] > 0
    for c in range(3):
        channel = arr[:, :, c].astype(np.int16)
        channel[alpha_mask] += noise[alpha_mask]
        arr[:, :, c] = np.clip(channel, 0, 255).astype(np.uint8)

    return Image.fromarray(arr, "RGBA")


def _add_neon_border(img, color="#000000", thickness=3, glow_radius=6, opacity=200):
    """Add a thin bright glowing line tracing the product silhouette."""
    img = img.convert("RGBA")
    rgb = hex_to_rgb(color) if isinstance(color, str) else color
    pad = glow_radius * 3 + thickness
    new_w = img.width + pad * 2
    new_h = img.height + pad * 2
    result = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))

    # Create dilated and eroded alpha to find the border region
    alpha = img.split()[3]
    alpha_padded = Image.new("L", (new_w, new_h), 0)
    alpha_padded.paste(alpha, (pad, pad))

    outer_k = 2 * thickness + 1
    outer = alpha_padded.filter(ImageFilter.MaxFilter(outer_k))
    # Border = outer minus original alpha
    outer_arr = np.array(outer, dtype=np.int16)
    inner_arr = np.array(alpha_padded, dtype=np.int16)
    border_arr = np.clip(outer_arr - inner_arr, 0, 255).astype(np.uint8)
    border_mask = Image.fromarray(border_arr)

    # Bright neon line layer
    neon_line = Image.new("RGBA", (new_w, new_h), (*rgb, opacity))
    neon_line.putalpha(border_mask)

    # Glow layer: blur the neon line for glow effect
    glow = neon_line.copy()
    glow = glow.filter(ImageFilter.GaussianBlur(radius=glow_radius))

    # Composite: glow behind, neon line on top, then product
    result = Image.alpha_composite(result, glow)
    result = Image.alpha_composite(result, neon_line)
    result.paste(img, (pad, pad), img)
    return result


def _apply_product_effects(img, effects, accent_color="#000000", collage=False):
    """Apply enabled visual effects to a product image in the correct order.

    effects: dict with bool values for each effect key
    collage: if True, skip reflection (too cluttered for collage frames)

    Order: polaroid -> outline -> neon_border -> glow -> shadow/float_shadow
           -> noise -> tilt -> sparkles -> reflection
    """
    img = img.convert("RGBA")

    if effects.get("polaroid"):
        img = _add_polaroid_frame(img, border=16, bottom_extra=40)

    if effects.get("outline"):
        img = _add_white_outline(img, thickness=4)

    if effects.get("neon_border"):
        img = _add_neon_border(img, color=accent_color, thickness=3,
                               glow_radius=6, opacity=200)

    if effects.get("glow"):
        img = _add_colored_glow(img, color=accent_color, radius=20, opacity=80)

    # Float shadow and drop shadow are mutually exclusive; float takes priority
    if effects.get("float_shadow"):
        img = _add_float_shadow(img, blur_radius=18, opacity=45, gap=20)
    elif effects.get("shadow"):
        img = _add_drop_shadow(img, offset=(6, 6), blur_radius=12, opacity=60)

    if effects.get("noise"):
        img = _add_noise_grain(img, intensity=25)

    if effects.get("tilt"):
        img = _add_tilt(img, max_angle=3.0)

    if effects.get("sparkles"):
        img = _add_sparkles(img, count=5)

    if effects.get("reflection") and not collage:
        img = _add_reflection(img, opacity=40, height_frac=0.3)

    return img


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
                      shuffle=True, effects=None, accent_color="#000000"):
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

        if effects:
            # Use full effects pipeline (collage=True skips reflection)
            prod_img = _apply_product_effects(prod_img, effects,
                                              accent_color=accent_color,
                                              collage=True)
        else:
            # Legacy behavior: just add drop shadow
            prod_img = _add_drop_shadow(prod_img, offset=(5, 5),
                                        blur_radius=10, opacity=50)

        if abs(angle) > 0.5:
            prod_img = prod_img.rotate(angle, resample=Image.BICUBIC,
                                       expand=True)

        img_x = px + (sw - prod_img.width) // 2
        img_y = py + (sh - prod_img.height) // 2
        paste_with_alpha(canvas, prod_img, (img_x, img_y))


# ==============================================================================
# Collage layout presets (title zone ~800-1150 kept clear)
# Format: (x, y, w, h, rotation_degrees)
# ==============================================================================

_LAYOUT_ORGANIC_CLUSTER = [
    # Top cluster — staggered heights, varied sizes
    (-30, -30, 400, 500, -10),    # top-left, large, bleeds off edge
    (320, 60, 320, 380, 6),       # top-center, medium, offset lower
    (620, -50, 460, 540, 8),      # top-right, large, bleeds top
    (160, 380, 220, 260, -14),    # mid-left, small accent
    # Bottom cluster — staggered, below title
    (-20, 1180, 440, 500, 7),     # bottom-left, large, bleeds edge
    (380, 1260, 340, 400, -5),    # bottom-center, offset lower
    (700, 1160, 400, 480, -9),    # bottom-right, large
    (240, 1520, 240, 280, 12),    # bottom-center-low, small accent
]

_LAYOUT_HERO_ASYMMETRIC = [
    # One hero product dominates
    (180, -20, 720, 740, -3),     # top-center HERO, huge
    # Supporting items — asymmetric, varied sizes
    (-40, 380, 260, 320, 12),     # left accent, small, rotated
    (820, 300, 240, 300, -8),     # right accent, small
    (-30, 1180, 480, 500, 6),     # bottom-left, large
    (440, 1240, 360, 420, -7),    # bottom-center
    (760, 1160, 340, 440, 10),    # bottom-right
    (600, 1500, 220, 260, -15),   # bottom low accent
]

_LAYOUT_DIAGONAL_SCATTER = [
    # Products flow along a diagonal / S-curve with edge bleeds
    (-40, -40, 420, 480, -12),    # top-left, bleeds corner
    (560, 80, 520, 560, 5),       # top-right, large, tilted
    (780, 500, 300, 340, -10),    # mid-right, small
    (-30, 440, 280, 320, 15),     # mid-left, small, rotated
    (60, 1180, 500, 520, 8),      # bottom-left, large
    (520, 1220, 540, 500, -6),    # bottom-right, large
    (300, 1540, 260, 280, 12),    # bottom-center-low, accent
]

COLLAGE_LAYOUTS = {
    "Organic Cluster": _LAYOUT_ORGANIC_CLUSTER,
    "Hero + Asymmetric": _LAYOUT_HERO_ASYMMETRIC,
    "Diagonal Scatter": _LAYOUT_DIAGONAL_SCATTER,
}


# ==============================================================================
# @AmazonHome -- Warm beige/cream with watermark pattern
# ==============================================================================

def _home_collage(products, theme_name="Just Dropped", effects=None, layout=None):
    pal = PALETTE["@AmazonHome"]
    bg = hex_to_rgb(pal["bg"])
    wm_color = hex_to_rgb(pal["watermark"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Watermark pattern
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color)

    # Scattered products
    positions = COLLAGE_LAYOUTS.get(layout, _LAYOUT_ORGANIC_CLUSTER)
    _scatter_products(canvas, products, positions,
                      effects=effects, accent_color=pal["accent"])

    # Title block -- centered horizontally & vertically in middle band
    draw = ImageDraw.Draw(canvas)
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 52)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 120)

    ty = H // 2 - 100

    month_text = _current_month()
    month_w = draw.textbbox((0, 0), month_text, font=month_font)[2]
    draw.text(((W - month_w) // 2, ty), month_text, font=month_font, fill=accent)

    title_w = draw.textbbox((0, 0), theme_name, font=title_font)[2]
    draw.text(((W - title_w) // 2, ty + 62), theme_name, font=title_font, fill=txt_color)

    return canvas


def _home_individual(product_data, frame_num=1, effects=None):
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
    max_w, max_h = (560, 740) if effects else (620, 820)
    prod_img = _prepare_product(product_data["image"], max_w, max_h)
    if effects:
        prod_img = _apply_product_effects(prod_img, effects, pal["accent"])
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

# Title zone ~800-1150 is kept clear
_BEAUTY_COLLAGE_POSITIONS = [
    (20, -10, 480, 560, -6),     # top-left, large, tilted
    (460, 30, 500, 540, 8),      # top-right, large, tilted opposite
    (-10, 1200, 500, 500, 5),    # bottom-left, below title
    (450, 1220, 520, 480, -7),   # bottom-right, below title
    (760, 420, 260, 300, 12),    # right accent, small, rotated
]

def _beauty_collage(products, theme_name="Just Dropped", effects=None, layout=None):
    pal = PALETTE["@AmazonBeauty"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)

    # Scattered products with mint circles -- behind title
    positions = COLLAGE_LAYOUTS.get(layout, _LAYOUT_ORGANIC_CLUSTER)
    _scatter_products(canvas, products, positions,
                      circle_color=pal["circle"],
                      effects=effects, accent_color=pal["accent"])

    # Title block -- centered horizontally & vertically in middle band
    draw = ImageDraw.Draw(canvas)
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 52)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 120)
    sub_font = ImageFont.truetype(FONT_TEXT_REGULAR, 32)

    ty = H // 2 - 110

    month_text = _current_month()
    month_w = draw.textbbox((0, 0), month_text, font=month_font)[2]
    draw.text(((W - month_w) // 2, ty), month_text, font=month_font, fill=accent)

    title_w = draw.textbbox((0, 0), theme_name, font=title_font)[2]
    draw.text(((W - title_w) // 2, ty + 62), theme_name, font=title_font, fill=txt_color)

    sub_text = "new beauty finds to add to cart"
    sub_w = draw.textbbox((0, 0), sub_text, font=sub_font)[2]
    draw.text(((W - sub_w) // 2, ty + 196), sub_text, font=sub_font, fill=accent)

    return canvas


def _beauty_individual(product_data, frame_num=1, effects=None):
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
    max_w, max_h = (500, 640) if effects else (580, 720)
    prod_img = _prepare_product(product_data["image"], max_w, max_h)
    if effects:
        prod_img = _apply_product_effects(prod_img, effects, pal["accent"])
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
# Title zone ~780-1180 is kept clear
_FASHION_COLLAGE_POSITIONS = [
    (440, -30, 600, 680, -5),    # top-right, HERO size, slight tilt
    (-20, 40, 460, 540, 7),      # top-left, medium, tilted
    (740, 440, 280, 320, -12),   # right accent, small, rotated
    (-30, 1220, 500, 480, 8),    # bottom-left, below title
    (460, 1200, 520, 500, -6),   # bottom-right, below title
    (180, 1460, 280, 340, 14),   # bottom-center accent, rotated
]

def _fashion_collage(products, theme_name="Just Dropped", effects=None, layout=None):
    pal = PALETTE["@AmazonFashion"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)

    # Products around title
    positions = COLLAGE_LAYOUTS.get(layout, _LAYOUT_ORGANIC_CLUSTER)
    _scatter_products(canvas, products, positions,
                      effects=effects, accent_color=pal["accent"])

    # Stacked editorial title -- centered
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 130)
    sub_font = ImageFont.truetype(FONT_TEXT_REGULAR, 28)

    ty = H // 2 - 120

    just_w = draw.textbbox((0, 0), "JUST", font=title_font)[2]
    draw.text(((W - just_w) // 2, ty), "JUST", font=title_font, fill=txt_color)

    dropped_w = draw.textbbox((0, 0), "DROPPED", font=title_font)[2]
    draw.text(((W - dropped_w) // 2, ty + 138), "DROPPED", font=title_font, fill=txt_color)

    sub_text = "DISCOVER MORE MUST-HAVES"
    sub_w = draw.textbbox((0, 0), sub_text, font=sub_font)[2]
    draw.text(((W - sub_w) // 2, ty + 286), sub_text, font=sub_font, fill=accent)

    # Fashion collage has CTA (per reference)
    _draw_cta_link(canvas, "AMAZON FASHION", accent, ty + 332)

    return canvas


def _fashion_individual(product_data, frame_num=1, effects=None):
    pal = PALETTE["@AmazonFashion"]
    bg = hex_to_rgb(pal["bg"])
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # Product -- EXTRA LARGE for fashion editorial feel
    max_w, max_h = (760, 980) if effects else (860, 1100)
    prod_img = _prepare_product(product_data["image"], max_w, max_h)
    if effects:
        prod_img = _apply_product_effects(prod_img, effects, pal["accent"])
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
# Title zone ~800-1150 is kept clear
_AMAZON_COLLAGE_POSITIONS = [
    (20, -10, 420, 500, -7),     # top-left, large, tilted
    (380, 20, 380, 460, 6),      # top-center, medium
    (720, -30, 360, 440, 10),    # top-right, tilted right
    (10, 1200, 400, 480, 5),     # bottom-left, below title
    (380, 1220, 380, 460, -8),   # bottom-center, below title
    (720, 1180, 360, 460, 7),    # bottom-right, below title
    (780, 440, 260, 300, -14),   # right accent, rotated
]

def _amazon_collage(products, theme_name="Just Dropped", gradient_idx=0,
                    effects=None, layout=None):
    pal = PALETTE["@Amazon"]
    gradients = pal["gradients"]
    g = gradients[gradient_idx % len(gradients)]

    canvas = _make_gradient(W, H, g[0], g[1])
    draw = ImageDraw.Draw(canvas)

    # Watermark -- use gradient-matched color (barely visible)
    wm_colors = pal["gradient_watermarks"]
    wm_color = hex_to_rgb(wm_colors[gradient_idx % len(wm_colors)])
    _draw_watermark_pattern(draw, "JUST DROPPED", wm_color)

    # Scattered products
    positions = COLLAGE_LAYOUTS.get(layout, _LAYOUT_ORGANIC_CLUSTER)
    _scatter_products(canvas, products, positions,
                      effects=effects, accent_color=pal["accent"])

    # Title -- centered
    draw = ImageDraw.Draw(canvas)
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 52)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 120)

    ty = H // 2 - 100

    month_text = _current_month()
    month_w = draw.textbbox((0, 0), month_text, font=month_font)[2]
    draw.text(((W - month_w) // 2, ty), month_text, font=month_font, fill=accent)

    title_w = draw.textbbox((0, 0), theme_name, font=title_font)[2]
    draw.text(((W - title_w) // 2, ty + 62), theme_name, font=title_font, fill=txt_color)

    return canvas


def _amazon_individual(product_data, frame_num=1, gradient_idx=0, effects=None):
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
    max_w, max_h = (560, 740) if effects else (620, 820)
    prod_img = _prepare_product(product_data["image"], max_w, max_h)
    if effects:
        prod_img = _apply_product_effects(prod_img, effects, pal["accent"])
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

def _ca_collage(products, theme_name="Just Dropped", lang="en", gradient_idx=0,
                effects=None, layout=None):
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
    positions = COLLAGE_LAYOUTS.get(layout, _LAYOUT_ORGANIC_CLUSTER)
    _scatter_products(canvas, products, positions,
                      effects=effects, accent_color=pal["accent"])

    # Title
    draw = ImageDraw.Draw(canvas)
    txt_color = hex_to_rgb(pal["text"])
    accent = hex_to_rgb(pal["accent"])
    month_font = ImageFont.truetype(FONT_DISPLAY_ITALIC, 52)
    title_font = ImageFont.truetype(FONT_DISPLAY_BOLD, 120)

    month = _current_month()
    if lang == "fr":
        month = _FR_MONTHS.get(month, month)
    title_text = "Tout juste sorti" if lang == "fr" else theme_name

    ty = H // 2 - 100

    month_w = draw.textbbox((0, 0), month, font=month_font)[2]
    draw.text(((W - month_w) // 2, ty), month, font=month_font, fill=accent)

    title_w = draw.textbbox((0, 0), title_text, font=title_font)[2]
    draw.text(((W - title_w) // 2, ty + 62), title_text, font=title_font, fill=txt_color)

    return canvas


def _ca_individual(product_data, frame_num=1, lang="en", gradient_idx=0,
                   effects=None):
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
    max_w, max_h = (560, 740) if effects else (620, 820)
    prod_img = _prepare_product(product_data["image"], max_w, max_h)
    if effects:
        prod_img = _apply_product_effects(prod_img, effects, pal["accent"])
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


def generate_franchise_frames(channel, products, theme_name="Just Dropped",
                              effects=None, layout=None):
    builders = CHANNEL_BUILDERS[channel]
    results = []

    gradient_idx = random.randint(0, 5)
    safe_channel = channel.replace("@", "").replace(".", "_")

    # Frame 1: Collage
    if channel in ("@Amazon", "@Amazon.ca"):
        if channel == "@Amazon.ca":
            collage_en = builders["collage"](products, theme_name, lang="en",
                                             gradient_idx=gradient_idx,
                                             effects=effects, layout=layout)
        else:
            collage_en = builders["collage"](products, theme_name,
                                             gradient_idx=gradient_idx,
                                             effects=effects, layout=layout)
    else:
        collage_en = builders["collage"](products, theme_name, effects=effects,
                                         layout=layout)

    collage_buf = _save_frame(collage_en)
    results.append((f"{safe_channel}/Frame_01_Collage.png", collage_buf))

    # Frames 2 to N+1: Individual product frames
    for i, prod in enumerate(products):
        frame_num = i + 1
        if channel == "@Amazon":
            frame = builders["individual"](prod, frame_num=frame_num,
                                           gradient_idx=(gradient_idx + i) % 6,
                                           effects=effects)
        elif channel == "@Amazon.ca":
            frame = builders["individual"](prod, frame_num=frame_num, lang="en",
                                           gradient_idx=(gradient_idx + i) % 6,
                                           effects=effects)
        else:
            frame = builders["individual"](prod, frame_num=frame_num,
                                           effects=effects)

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
                                         gradient_idx=gradient_idx,
                                         effects=effects, layout=layout)
        fr_buf = _save_frame(collage_fr)
        results.append((f"{safe_channel}_FR/Frame_01_Collage.png", fr_buf))

        for i, prod in enumerate(products):
            frame_fr = builders["individual"](prod, frame_num=i+1, lang="fr",
                                              gradient_idx=(gradient_idx + i) % 6,
                                              effects=effects)
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
