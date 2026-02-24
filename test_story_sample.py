"""
Generate sample Just Dropped story frames with real product images.
Outputs horizontal strip previews (all cards side by side) matching reference format.

Usage:
  python test_story_sample.py                   # local, no bg removal
  python test_story_sample.py --remove-bg       # with background removal (needs transparent-background)
  python test_story_sample.py --output-dir /path/to/dir  # custom output directory
"""

import os
import re
import sys
import time
import argparse
import requests
from io import BytesIO
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import story_engine

# Default output dirs per platform
if sys.platform == "win32":
    _DEFAULT_OUTPUT = r"C:\Users\awictor\Documents\ILM_Banner_Generator\Just Dropped Instagram Story Franchise Generator"
else:
    _DEFAULT_OUTPUT = os.path.expanduser("~/just_dropped_output")


def _next_sample_dir(base_dir):
    """Find the next 'Sample N' folder number and create it."""
    os.makedirs(base_dir, exist_ok=True)
    existing = [
        d for d in os.listdir(base_dir)
        if os.path.isdir(os.path.join(base_dir, d)) and d.startswith("Sample ")
    ]
    nums = []
    for d in existing:
        try:
            nums.append(int(d.split("Sample ")[1]))
        except (ValueError, IndexError):
            pass
    next_num = max(nums, default=0) + 1
    sample_dir = os.path.join(base_dir, f"Sample {next_num}")
    os.makedirs(sample_dir, exist_ok=True)
    return sample_dir


def _remove_bg(img):
    """Remove background using transparent-background library."""
    from transparent_background import Remover
    remover = Remover()
    img_rgb = img.convert("RGB")
    result = remover.process(img_rgb, type="rgba")
    return result.convert("RGBA")

# ── Sample data (9 products per channel -> 11 cards total) ───────
# ASINs are real Amazon products chosen for reliable image availability.
SAMPLE_PRODUCTS = {
    "@AmazonHome": [
        {"asin": "B0BSHF7WHW", "brand": "Casaluna", "product_name": "Martini Glasses", "copy": "Cheers to hosting and serving guests with real crystal"},
        {"asin": "B09JNR3PKM", "brand": "Our Place", "product_name": "Always Pan", "copy": "Cook with less oil than traditional frying methods for holiday meals"},
        {"asin": "B07VFCMJZS", "brand": "Keurig", "product_name": "K-Mini Coffee Maker", "copy": "Make your own single-serve coffee right at home"},
        {"asin": "B08CF3B7N1", "brand": "Casaluna", "product_name": "Linen Duvet Cover", "copy": "Soft stonewashed linen for effortless bedroom style"},
        {"asin": "B07FJ5XQJT", "brand": "Lodge", "product_name": "Cast Iron Skillet", "copy": "Sear, saute, and bake with a single pan"},
        {"asin": "B073429DLW", "brand": "Instant Pot", "product_name": "Duo 7-in-1", "copy": "Seven kitchen appliances in one pot"},
        {"asin": "B0B2WQFFHG", "brand": "Stanley", "product_name": "Quencher Tumbler", "copy": "Keeps drinks cold for hours with vacuum insulation"},
        {"asin": "B07YDC5GHV", "brand": "Le Creuset", "product_name": "Dutch Oven", "copy": "Cook one-pot meals or bake a loaf of bread in enameled cast iron"},
        {"asin": "B09HBG3XBZ", "brand": "Nespresso", "product_name": "Vertuo Next", "copy": "One-touch barista-quality coffee at home"},
    ],
    "@AmazonBeauty": [
        {"asin": "B0B1DJNFCH", "brand": "Drunk Elephant", "product_name": "Protini Moisturizer", "copy": "Signal peptides and growth factors deliver smooth hydrated skin"},
        {"asin": "B003WN1ELQ", "brand": "CeraVe", "product_name": "Moisturizing Cream", "copy": "24-hour hydration with essential ceramides"},
        {"asin": "B004Y9GZDO", "brand": "Thayers", "product_name": "Witch Hazel Toner", "copy": "Alcohol-free toner that cleanses and tones skin naturally"},
        {"asin": "B00TTD9BRC", "brand": "Neutrogena", "product_name": "Hydro Boost Gel", "copy": "Quenches dry skin instantly with hyaluronic acid"},
        {"asin": "B0048ZIFA2", "brand": "Bioderma", "product_name": "Micellar Water", "copy": "Gently removes makeup while respecting your skin"},
        {"asin": "B01MSSDEPK", "brand": "Mario Badescu", "product_name": "Facial Spray", "copy": "Rejuvenate and refresh skin throughout the day"},
        {"asin": "B07SNCBMM7", "brand": "Tatcha", "product_name": "Dewy Skin Cream", "copy": "Plumping and hydrating for a dewy glow"},
        {"asin": "B000GDQ0T0", "brand": "La Roche-Posay", "product_name": "Toleriane Cleanser", "copy": "Gentle face wash for sensitive skin"},
        {"asin": "B01N7T41WR", "brand": "Herbivore", "product_name": "Lapis Face Oil", "copy": "Lightweight hydrating serum with natural botanicals"},
    ],
    "@AmazonFashion": [
        {"asin": "B098RLHQC1", "brand": "Levi's", "product_name": "501 Original Jeans", "copy": "The original jean that started it all"},
        {"asin": "B09HGWZM9J", "brand": "Beis", "product_name": "Carry-On Roller", "copy": "Never work harder than your carry-on again"},
        {"asin": "B08W57G8L5", "brand": "Adidas", "product_name": "Ultraboost", "copy": "Energy-returning comfort for every run"},
        {"asin": "B07N4GCQ4Q", "brand": "Ray-Ban", "product_name": "Classic Aviator", "copy": "Iconic style that never goes out of fashion"},
        {"asin": "B07WFCMBXT", "brand": "Herschel", "product_name": "Classic Backpack", "copy": "Timeless design meets everyday functionality"},
        {"asin": "B09KLCYSF4", "brand": "New Balance", "product_name": "574 Sneakers", "copy": "Classic sneakers reimagined for everyday wear"},
        {"asin": "B0B6YR1LZN", "brand": "Calvin Klein", "product_name": "Modern Cotton Bralette", "copy": "Everyday comfort with signature style"},
        {"asin": "B0BQVPL3GD", "brand": "The Drop", "product_name": "Wide Leg Pants", "copy": "Entering 2026 with elevated everyday pieces"},
        {"asin": "B07HHN6KBZ", "brand": "Champion", "product_name": "Reverse Weave Hoodie", "copy": "Classic athletic comfort meets street style"},
    ],
    "@Amazon": [
        {"asin": "B0BDJF16PM", "brand": "CurrentBody", "product_name": "LED Face Mask", "copy": "The glow tool everyone is adding to their routine"},
        {"asin": "B0CHX3QBCH", "brand": "Jolie", "product_name": "Filtered Showerhead", "copy": "Turn every shower into a skin and hair reset"},
        {"asin": "B0CGXKZTBQ", "brand": "Balmuda", "product_name": "The Toaster", "copy": "Steam technology creates the perfect toast"},
        {"asin": "B0BT7D5K84", "brand": "Blissy", "product_name": "Silk Pillowcase", "copy": "Where sleep becomes a beauty treatment"},
        {"asin": "B09V3KXJPB", "brand": "Ember", "product_name": "Smart Mug 2", "copy": "Your favorite drinks exactly how you like them"},
        {"asin": "B07QK955LS", "brand": "Dyson", "product_name": "Airwrap Styler", "copy": "Style and dry simultaneously with no heat damage"},
        {"asin": "B08N5WRWNW", "brand": "Apple", "product_name": "AirTag", "copy": "Keep track of and find your items alongside friends and devices"},
        {"asin": "B09JQMJHXY", "brand": "Sony", "product_name": "WH-1000XM5", "copy": "Industry-leading noise cancellation for total focus"},
        {"asin": "B0931YZ6TL", "brand": "Kindle", "product_name": "Paperwhite", "copy": "The upgraded e-reader with warm adjustable light"},
    ],
    "@Amazon.ca": [
        {"asin": "B0D1XD1ZV3", "brand": "Apple", "product_name": "AirPods Pro 2", "copy": "Adaptive audio with personalized spatial sound"},
        {"asin": "B0B2WQFFHG", "brand": "Stanley", "product_name": "Quencher Tumbler", "copy": "Keeps drinks cold for 11 hours"},
        {"asin": "B09HBG3XBZ", "brand": "Nespresso", "product_name": "Vertuo Next", "copy": "One-touch barista-quality coffee at home"},
        {"asin": "B07QK955LS", "brand": "Dyson", "product_name": "Airwrap Styler", "copy": "Style and dry with no heat damage"},
        {"asin": "B0931YZ6TL", "brand": "Kindle", "product_name": "Paperwhite", "copy": "Upgraded e-reader with wireless charging"},
        {"asin": "B09JQMJHXY", "brand": "Sony", "product_name": "WH-1000XM5", "copy": "World-class noise cancellation for total focus"},
        {"asin": "B08N5WRWNW", "brand": "Apple", "product_name": "AirTag", "copy": "Precision finding with Ultra Wideband technology"},
        {"asin": "B073429DLW", "brand": "Instant Pot", "product_name": "Duo 7-in-1", "copy": "Restaurant-quality cooking at home"},
        {"asin": "B003WN1ELQ", "brand": "CeraVe", "product_name": "Moisturizing Cream", "copy": "Dermatologist-recommended daily hydration"},
    ],
}


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _download_image(url):
    """Download an image URL and return as RGBA PIL Image, or None on failure."""
    resp = requests.get(url, timeout=12, headers=_HEADERS)
    resp.raise_for_status()
    img = Image.open(BytesIO(resp.content)).convert("RGBA")
    # Reject tiny/broken images (Amazon returns 1x1 px for missing products)
    if img.size[0] < 80 or img.size[1] < 80:
        return None
    return img


def fetch_amazon_image(asin, label, domain="com"):
    """Fetch product image from Amazon product page by ASIN.

    Tries multiple extraction patterns from the product page HTML,
    then falls back to DDG image search, then placeholder.
    """
    amazon_url = f"https://www.amazon.{domain}/dp/{asin}"
    print(f"  Amazon ({domain}): {amazon_url}")

    # --- Method 1: Scrape Amazon product page for image URL ---
    try:
        resp = requests.get(amazon_url, headers=_HEADERS, timeout=15)
        if resp.status_code == 200:
            html = resp.text
            img_url = None

            # Pattern 1: hiRes in image data JSON
            m = re.search(r'"hiRes"\s*:\s*"(https://m\.media-amazon\.com/images/I/[^"]+)"', html)
            if m:
                img_url = m.group(1)

            # Pattern 2: data-old-hires attribute on main image
            if not img_url:
                m = re.search(r'data-old-hires="(https://[^"]+)"', html)
                if m:
                    img_url = m.group(1)

            # Pattern 3: og:image meta tag
            if not img_url:
                m = re.search(r'<meta\s+(?:property|name)="og:image"\s+content="([^"]+)"', html)
                if m:
                    img_url = m.group(1)

            # Pattern 4: landingImage src
            if not img_url:
                m = re.search(r'id="landingImage"[^>]+src="(https://[^"]+)"', html)
                if m:
                    img_url = m.group(1)

            # Pattern 5: Any m.media-amazon image larger than thumbnails
            if not img_url:
                m = re.search(r'"(https://m\.media-amazon\.com/images/I/[^"]+_(?:AC_SL1500|SX679|SY741|SL1200)[^"]*\.jpg)"', html)
                if m:
                    img_url = m.group(1)

            if img_url:
                print(f"  Found image: {img_url[:80]}...")
                img = _download_image(img_url)
                if img:
                    print(f"  OK ({img.size[0]}x{img.size[1]})")
                    return img
                print(f"  Image too small or broken, trying next method")
        else:
            print(f"  Amazon returned {resp.status_code}")
    except Exception as e:
        print(f"  Amazon page scrape failed: {e}")

    # --- Method 2: DDG image search fallback ---
    try:
        from duckduckgo_search import DDGS
        query = f"amazon {asin} product"
        print(f"  DDG fallback: {query}")
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=3))
        for r in results:
            url = r.get("image", "")
            if not url:
                continue
            try:
                img = _download_image(url)
                if img:
                    print(f"  DDG OK ({img.size[0]}x{img.size[1]})")
                    return img
            except Exception:
                continue
    except Exception as e:
        print(f"  DDG search failed: {e}")

    print(f"  All methods failed, using placeholder for {label}")
    return _make_placeholder(label)


def _make_placeholder(label):
    img = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([50, 50, 450, 450], radius=30, fill=(180, 180, 200, 220))
    draw.text((100, 230), label[:20], fill=(255, 255, 255, 255))
    return img


def make_horizontal_strip(frames, card_height=800):
    """Combine all frames into a horizontal strip preview (like reference images).

    Each frame is scaled to card_height tall, laid out side by side on white bg.
    """
    # Scale each frame
    scaled = []
    for fname, buf in frames:
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
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


def main():
    parser = argparse.ArgumentParser(description="Generate Just Dropped sample frames")
    parser.add_argument("--remove-bg", action="store_true",
                        help="Remove background from product images")
    parser.add_argument("--output-dir", default=_DEFAULT_OUTPUT,
                        help="Base output directory")
    args = parser.parse_args()

    OUTPUT_DIR = _next_sample_dir(args.output_dir)
    print(f"Output folder: {OUTPUT_DIR}")
    print(f"Background removal: {'ON' if args.remove_bg else 'OFF'}")

    # Pre-load the bg remover once if needed
    remover = None
    if args.remove_bg:
        print("Loading background removal model...")
        from transparent_background import Remover
        remover = Remover()
        print("Model loaded.")

    franchise_data = {}
    theme_names = {
        "@AmazonHome": "Just Dropped",
        "@AmazonBeauty": "Just Dropped",
        "@AmazonFashion": "Just Dropped",
        "@Amazon": "Just Dropped",
        "@Amazon.ca": "Just Dropped",
    }

    for channel, items in SAMPLE_PRODUCTS.items():
        print(f"\n{'='*50}")
        print(f"Fetching images for {channel} ({len(items)} products)")
        print(f"{'='*50}")

        # Use .ca domain for Amazon.ca ASINs
        domain = "ca" if channel == "@Amazon.ca" else "com"

        products = []
        for item in items:
            img = fetch_amazon_image(item["asin"], item["product_name"], domain=domain)

            # Remove background if enabled
            if remover is not None:
                try:
                    print(f"  Removing background...")
                    img_rgb = img.convert("RGB")
                    img = remover.process(img_rgb, type="rgba").convert("RGBA")
                    print(f"  BG removed OK")
                except Exception as e:
                    print(f"  BG removal failed: {e}, using original")

            products.append({
                "asin": item["asin"],
                "brand": item["brand"],
                "product_name": item["product_name"],
                "copy": item["copy"],
                "image": img,
            })
            time.sleep(0.5)

        franchise_data[channel] = products

    print(f"\n{'='*50}")
    print("Generating frames...")
    print(f"{'='*50}")

    # Generate per channel and save both individual frames + horizontal strip
    for channel, products in franchise_data.items():
        theme = theme_names.get(channel, "Just Dropped")
        frames = story_engine.generate_franchise_frames(channel, products, theme)

        safe_channel = channel.replace("@", "").replace(".", "_")

        # Save individual frames
        frame_dir = os.path.join(OUTPUT_DIR, safe_channel)
        os.makedirs(frame_dir, exist_ok=True)
        for fname, buf in frames:
            # fname already has channel prefix, strip it for the subfolder
            base = os.path.basename(fname)
            fpath = os.path.join(frame_dir, base)
            buf.seek(0)
            with open(fpath, "wb") as f:
                f.write(buf.read())

        # Save horizontal strip preview
        if channel == "@Amazon.ca":
            # Split EN and FR into separate strips
            en_frames = [(f, b) for f, b in frames if "_FR/" not in f]
            fr_frames = [(f, b) for f, b in frames if "_FR/" in f]

            strip_en = make_horizontal_strip(en_frames)
            strip_en_path = os.path.join(OUTPUT_DIR, f"Just Dropped_{safe_channel}_EN_strip.jpg")
            strip_en.save(strip_en_path, "JPEG", quality=92)
            print(f"  {safe_channel} EN: {len(en_frames)} frames -> {strip_en_path}")

            strip_fr = make_horizontal_strip(fr_frames)
            strip_fr_path = os.path.join(OUTPUT_DIR, f"Just Dropped_{safe_channel}_FR_strip.jpg")
            strip_fr.save(strip_fr_path, "JPEG", quality=92)
            print(f"  {safe_channel} FR: {len(fr_frames)} frames -> {strip_fr_path}")
        else:
            strip = make_horizontal_strip(frames)
            strip_path = os.path.join(OUTPUT_DIR, f"Just Dropped_{safe_channel}_strip.jpg")
            strip.save(strip_path, "JPEG", quality=92)
            print(f"  {safe_channel}: {len(frames)} frames -> {strip_path}")

    print(f"\nDone! Output saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
