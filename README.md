# ILM Banner Generator

Multi-page Streamlit web app that generates banner ads and Instagram Story frames for Amazon ILM (Influencer/Lifestyle Marketing) brands.

## Quick Start (Local)

**Requirements:** Python 3.11, pip, git, ~8 GB disk space, 8–16 GB RAM

```bash
git clone https://github.com/awictor/ilm-banner-generator.git
cd ilm-banner-generator
pip3.11 install -r requirements.txt
python3.11 -m streamlit run app.py --server.port 8501 --server.headless true
```

Open `http://localhost:8501` in your browser.

## Quick Start (Docker)

```bash
git clone https://github.com/awictor/ilm-banner-generator.git
cd ilm-banner-generator
docker build -t ilm-banner-generator .
docker run -d -p 8501:8080 ilm-banner-generator
```

## What's Inside

| Page | Description |
|---|---|
| **ILM Banner Generator** | Creates banner ads in 6 sizes x 2 languages (ENG/ESP) = 12 assets per brand |
| **ILM Banner Generator – Canada** | Same banners with CA naming (ENG/FRA) |
| **ILM Banner Sliders** | Banners with real-time slider controls for element positioning; supports 1 or 2 product images |
| **Just Dropped Generator** | Instagram Story frames for @AmazonHome, @AmazonBeauty, @AmazonFashion, @Amazon, @Amazon.ca |
| **Just Dropped Simulator** | Quick-fire story preview with 10 toggleable visual effects and 3 collage layout presets |

## Project Structure

```
ilm-banner-generator/
├── app.py                       # Entry point (home page, optional password gate)
├── banner_engine.py             # Banner ad generation engine
├── banner_engine_sliders.py     # Banner engine with slider-parameterized positions
├── story_engine.py              # Instagram Story frame engine (effects, collage layouts)
├── story_themes.py              # Theme definitions for Just Dropped stories
├── shared.py                    # Shared utilities (image picker, AI background removal)
├── sample_products.py           # Sample product library for the simulator
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker build (exposes port 8080)
├── userdata.sh                  # EC2 user data for automated AWS deployment
├── SETUP_GUIDE.md               # Full deployment guide (local, AWS EC2, Docker, troubleshooting)
├── Fonts/
│   ├── EmberModernDisplay/      # Bold, BoldItalic, Italic, Regular (.otf)
│   └── EmberModernText/         # Bold, BoldItalic, Italic, Regular (.otf)
└── pages/
    ├── 1_ILM_Banner_Generator.py
    ├── 2_Just_Dropped_Generator.py
    ├── 3_ILM_Banner_Generator_CA.py
    ├── 4_ILM_Banner_Sliders.py
    └── 5_Just_Dropped_Simulator.py
```

## Dependencies

The `requirements.txt` installs these direct dependencies:

```
streamlit==1.41.1
Pillow==11.1.0
numpy==2.2.3
requests==2.32.3
duckduckgo-search==7.3.2
transparent-background
openpyxl==3.1.5
```

`transparent-background` pulls in PyTorch, onnxruntime, opencv, scikit-image, scipy, etc. (~7 GB total). This powers the AI background removal feature (InSPyReNet model running on CPU).

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BRAVE_API_KEY` | No | Brave Search API key for web search features |
| `APP_PASSWORD` | No | If set, enables a password gate on the home page |

Set them before running:
```bash
export BRAVE_API_KEY="your-key"
export APP_PASSWORD="your-password"
```

## AWS EC2 Deployment

For full AWS deployment instructions (EC2 instance setup, systemd service, security groups, SSM deploy workflow), see **[SETUP_GUIDE.md](SETUP_GUIDE.md)**.

**TL;DR** — Launch an Amazon Linux 2023 `c5.2xlarge` with the `userdata.sh` script as User Data. It auto-installs everything and starts the app on port 8501.

## Key Technical Details

- **Python 3.11** required (tested with 3.11.14)
- **Streamlit 1.41.1** multi-page app — pages are auto-discovered from `pages/` directory
- **Banner sizes**: 1300x90, 1200x90, 640x90 (full + half-size variants) + 75x75 HQP thumbnail
- **Story frames**: 1080x1920 Instagram Story format, supports 1–9 products per set
- **Background removal**: Uses `transparent-background` (InSPyReNet) on CPU with max_dim=512. First call loads the model (~7 GB RAM), subsequent calls are faster.
- **Fonts**: Amazon Ember Modern Display/Text bundled in `Fonts/` directory
- **Visual effects**: Drop shadow, white outline, accent glow, tilt, sparkles, reflection, float shadow, polaroid frame, noise/grain, neon border
- **Collage layouts**: Organic Cluster, Hero+Asymmetric, Diagonal Scatter (selectable presets)
