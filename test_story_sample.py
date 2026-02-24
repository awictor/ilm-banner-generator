"""
Generate sample Just Dropped story frames with real product images.
Outputs horizontal strip previews (all cards side by side) matching reference format.
"""

import os
import sys
import time
import requests
from io import BytesIO
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import story_engine

BASE_OUTPUT_DIR = r"C:\Users\awictor\Documents\ILM_Banner_Generator\Just Dropped Instagram Story Franchise Generator"


def _next_sample_dir():
    """Find the next 'Sample N' folder number and create it."""
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    existing = [
        d for d in os.listdir(BASE_OUTPUT_DIR)
        if os.path.isdir(os.path.join(BASE_OUTPUT_DIR, d)) and d.startswith("Sample ")
    ]
    nums = []
    for d in existing:
        try:
            nums.append(int(d.split("Sample ")[1]))
        except (ValueError, IndexError):
            pass
    next_num = max(nums, default=0) + 1
    sample_dir = os.path.join(BASE_OUTPUT_DIR, f"Sample {next_num}")
    os.makedirs(sample_dir, exist_ok=True)
    return sample_dir

# ── Sample data (9 products per channel -> 11 cards total) ───────
SAMPLE_PRODUCTS = {
    "@AmazonHome": [
        {"asin": "B0BSHF7WHW", "brand": "Casaluna", "product_name": "Martini Glasses", "copy": "Cheers to hosting and serving guests with real crystal", "query": "martini glasses set product white background"},
        {"asin": "B09JNR3PKM", "brand": "Our Place", "product_name": "Air Fryer", "copy": "Cook with less oil than traditional frying methods for holiday meals", "query": "air fryer product photo white background"},
        {"asin": "B0C5H5KNTQ", "brand": "Vitruvi", "product_name": "Kitchen Storage Organizer", "copy": "Storage that sparks joy and keeps your bags handy", "query": "kitchen storage organizer product white background"},
        {"asin": "B0BQ9ZTMCX", "brand": "Threshold", "product_name": "Duffle Bag", "copy": "Carry it all in a spacious bag with a padded laptop sleeve", "query": "travel duffle bag product white background"},
        {"asin": "B0D1K2MQWX", "brand": "Keurig", "product_name": "Coffee Pod Maker", "copy": "Make your own reusable coffee pods right at home", "query": "coffee pod maker machine product white background"},
        {"asin": "B0C7RLQM8Y", "brand": "Threshold", "product_name": "Sherpa Blanket", "copy": "Wrap yourself in warmth all season long", "query": "sherpa throw blanket product white background"},
        {"asin": "B0D3KXNM9Z", "brand": "W&P", "product_name": "Glass Cloud Cup", "copy": "Sip hot or cold drinks from a double-walled insulated cup", "query": "double wall glass cup product white background"},
        {"asin": "B0BN72BFRD", "brand": "Great Jones", "product_name": "Dutch Oven", "copy": "Cook one-pot meals or bake a loaf of bread in a cast iron pot", "query": "cast iron dutch oven product white background"},
        {"asin": "B0C8MNPQ3R", "brand": "Casaluna", "product_name": "Linen Pillow", "copy": "Soft stonewashed linen for effortless bedroom style", "query": "linen throw pillow product white background"},
    ],
    "@AmazonBeauty": [
        {"asin": "B0C1K2LQMW", "brand": "Drunk Elephant", "product_name": "Calming Facial Oil", "copy": "Use as last step in your routine for lasting moisture", "query": "facial oil serum product white background"},
        {"asin": "B09TPGBKJY", "brand": "Emerald", "product_name": "Hydration Mist", "copy": "Enhance skin elasticity and firmness with a few mists throughout the day", "query": "face mist spray product white background"},
        {"asin": "B0843MRJJZ", "brand": "Remedy", "product_name": "Dermatologist Bundle", "copy": "Comprehensive face and lip care in a value-packed bundle", "query": "skincare bundle set product white background"},
        {"asin": "B07ZPKBL93", "brand": "Nature", "product_name": "Brush Duo", "copy": "Apply foundation and concealer effortlessly with expertly designed brushes", "query": "makeup brush set product white background"},
        {"asin": "B0D2KXNQ4M", "brand": "Freaks", "product_name": "Balancing Cleanser", "copy": "Unique balance of probiotics and oils help improve skin barrier function", "query": "facial cleanser product white background"},
        {"asin": "B0C9MNRQ5P", "brand": "PRE", "product_name": "Lip Tint", "copy": "Visibly plumps lips reduces fine lines and protects from sun damage", "query": "lip tint product white background"},
        {"asin": "B0D4LXPQ6R", "brand": "The Outset", "product_name": "Daily Moisturizer", "copy": "Clinically proven to provide immediate and lasting hydration", "query": "daily moisturizer product white background"},
        {"asin": "B0C3DRJXNM", "brand": "SK-II", "product_name": "Glow Up Duo", "copy": "Your shortcut set to radiant skin", "query": "skincare duo set product white background"},
        {"asin": "B0D5MYQR7S", "brand": "Herbivore", "product_name": "Face Serum", "copy": "Lightweight hydrating serum with natural botanicals", "query": "face serum bottle product white background"},
    ],
    "@AmazonFashion": [
        {"asin": "B0B6YR1LZN", "brand": "Telfar", "product_name": "Mini Dress", "copy": "In case you needed a reason to go out", "query": "mini dress fashion product white background"},
        {"asin": "B0BQVPL3GD", "brand": "Jenny Bird", "product_name": "Earrings", "copy": "Your new go-to pair", "query": "gold hoop earrings product white background"},
        {"asin": "B09HGWZM9J", "brand": "Beis", "product_name": "Carry-On", "copy": "Never work harder than your carry-on again", "query": "carry on luggage suitcase product white background"},
        {"asin": "B0C3DRJXNM", "brand": "Telfar", "product_name": "Telfar Bag", "copy": "A pop of color for your weekly bag lineup", "query": "telfar shopping bag product photo"},
        {"asin": "B0D6NZRS8T", "brand": "Jenny Bird", "product_name": "Earrings Set", "copy": "Our fave gifts come in small packages", "query": "gold earring set jewelry product white background"},
        {"asin": "B0D7PASS9U", "brand": "Levi's", "product_name": "Jeans", "copy": "Entering 2026 and taking wide-leg jeans with us", "query": "wide leg jeans product white background"},
        {"asin": "B0D8QBTT0V", "brand": "Jenny Bird", "product_name": "Earrings Collection", "copy": "A bold new look for your earring rotation", "query": "statement earrings product white background"},
        {"asin": "B0D9RCUU1W", "brand": "Nike", "product_name": "Running Shorts", "copy": "Tackle your New Year's resolutions", "query": "running shorts product white background"},
        {"asin": "B0DASDVV2X", "brand": "The Drop", "product_name": "Blazer", "copy": "Elevated office-to-evening layering piece", "query": "womens blazer product white background"},
    ],
    "@Amazon": [
        {"asin": "B0BDJF16PM", "brand": "LED", "product_name": "Red Light Mask", "copy": "The glow tool everyone's adding to their routine", "query": "led face mask skincare product white background"},
        {"asin": "B0CHX3QBCH", "brand": "Jolie", "product_name": "Filtered Showerhead", "copy": "Turn every shower into a skin and hair reset", "query": "filtered showerhead product white background"},
        {"asin": "B0CGXKZTBQ", "brand": "Chilloutere", "product_name": "Board Set", "copy": "Hosting level expert down to the temperature", "query": "charcuterie board set product white background"},
        {"asin": "B0BT7D5K84", "brand": "SPI", "product_name": "Silk Pillowcase", "copy": "Where sleep becomes a beauty treatment", "query": "silk pillowcase product white background"},
        {"asin": "B0DBTEWW3Y", "brand": "Factory", "product_name": "Facial Moisturizer", "copy": "Your daily dose of moisturizing skin barrier support", "query": "facial moisturizer product white background"},
        {"asin": "B0DCUFXX4Z", "brand": "Martha Stewart", "product_name": "Pajamas", "copy": "Timeless style meets all-day cozy", "query": "pajamas set product white background"},
        {"asin": "B0DDVGYY50", "brand": "SK-II", "product_name": "Glow Up Duo", "copy": "Your shortcut set to radiant skin", "query": "skincare set box product white background"},
        {"asin": "B0DEWHZZ61", "brand": "Threshold", "product_name": "Faux Fur Throw Blanket", "copy": "Turn anywhere into the coziest corner", "query": "faux fur blanket product white background"},
        {"asin": "B0DFXIAA72", "brand": "Ember", "product_name": "Smart Mug", "copy": "Your favorite drinks exactly how you like them", "query": "ember smart mug product white background"},
    ],
    "@Amazon.ca": [
        {"asin": "B0BDJF16PM", "brand": "Apple", "product_name": "AirPods Pro 2", "copy": "Adaptive audio with personalized spatial sound", "query": "Apple AirPods Pro product white background"},
        {"asin": "B0CHX3QBCH", "brand": "Stanley", "product_name": "Quencher Tumbler", "copy": "Keeps drinks cold for 11 hours", "query": "Stanley Quencher tumbler product white background"},
        {"asin": "B09V3KXJPB", "brand": "Nespresso", "product_name": "Vertuo Next", "copy": "One-touch barista-quality coffee at home", "query": "Nespresso Vertuo Next product white background"},
        {"asin": "B0BN72BFRD", "brand": "Dyson", "product_name": "Supersonic Dryer", "copy": "Fast drying with no heat damage", "query": "Dyson Supersonic hair dryer product white background"},
        {"asin": "B0DGYJBB83", "brand": "Kindle", "product_name": "Paperwhite", "copy": "Upgraded e-reader with wireless charging", "query": "Kindle Paperwhite product white background"},
        {"asin": "B0DHZKCC94", "brand": "JBL", "product_name": "Charge 5 Speaker", "copy": "Powerful portable sound with IP67 waterproofing", "query": "JBL Charge 5 speaker product white background"},
        {"asin": "B0DIALDD05", "brand": "Lululemon", "product_name": "Belt Bag", "copy": "Hands-free convenience for your everyday essentials", "query": "belt bag product white background"},
        {"asin": "B0DJBMEE16", "brand": "Vitamix", "product_name": "Blender", "copy": "Restaurant-quality blending at home", "query": "vitamix blender product white background"},
        {"asin": "B0DKCNFF27", "brand": "Bose", "product_name": "QuietComfort Headphones", "copy": "World-class noise cancellation for total focus", "query": "Bose headphones product white background"},
    ],
}


def search_and_fetch(query, label):
    """Search DDG for an image, download first result."""
    try:
        from duckduckgo_search import DDGS
        print(f"  Searching: {query[:60]}...")
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=3))
        if not results:
            print(f"  No results, using placeholder")
            return _make_placeholder(label)

        for r in results:
            url = r.get("image", "")
            if not url:
                continue
            try:
                print(f"  Downloading: {url[:80]}...")
                resp = requests.get(url, timeout=10, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                resp.raise_for_status()
                img = Image.open(BytesIO(resp.content)).convert("RGBA")
                print(f"  OK ({img.size[0]}x{img.size[1]})")
                return img
            except Exception as e:
                print(f"  Failed: {e}")
                continue

        print(f"  All downloads failed, using placeholder")
        return _make_placeholder(label)
    except Exception as e:
        print(f"  Search failed: {e}, using placeholder")
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
    OUTPUT_DIR = _next_sample_dir()
    print(f"Output folder: {OUTPUT_DIR}")

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

        products = []
        for item in items:
            img = search_and_fetch(item["query"], item["product_name"])
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
