# ILM Banner Generator — Setup & Deployment Guide

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [File Structure](#file-structure)
4. [Prerequisites](#prerequisites)
5. [Option A: Local Setup](#option-a-local-setup)
6. [Option B: AWS EC2 Deployment](#option-b-aws-ec2-deployment)
7. [Option C: Docker](#option-c-docker)
8. [Environment Variables](#environment-variables)
9. [S3 Buckets](#s3-buckets)
10. [Security Group Configuration](#security-group-configuration)
11. [Deploying Code Updates](#deploying-code-updates)
12. [Troubleshooting](#troubleshooting)
13. [Current Production Details](#current-production-details)

---

## Project Overview

ILM Banner Generator is a multi-page Streamlit web application that generates banner ads and Instagram Story frames for Amazon ILM (Influencer/Lifestyle Marketing) brands. It includes:

- **ILM Banner Generator** — Creates banner ads in 6 sizes x 2 languages (ENG/ESP) = 12 assets per brand
- **ILM Banner Generator – Canada** — Same banners with CA naming convention (ENG/FRA)
- **ILM Banner Sliders** — Same banners with real-time slider controls to adjust element positions; supports 1 or 2 product images
- **Just Dropped Generator** — Creates Instagram Story frames for Amazon channel accounts
- **Just Dropped Simulator** — Quick-fire preview tool with visual effects (shadow, outline, glow, tilt, sparkles, reflection, polaroid, neon border, etc.) and collage layout presets

The app uses AI-powered background removal (InSPyReNet via `transparent-background`) for product images.

---

## Architecture

```
GitHub Repo (awictor/ilm-banner-generator)
        |
        | git pull
        v
EC2 Instance (us-east-1, c5.2xlarge)
  - Amazon Linux 2023, x86_64
  - Python 3.11
  - Streamlit runs as systemd service on port 8501
  - Security group restricts access to whitelisted IPs
```

---

## File Structure

```
ilm-banner-generator/
├── app.py                          # Main entry point (home page, password gate)
├── banner_engine.py                # Banner ad generation engine (standard)
├── banner_engine_sliders.py        # Banner engine with slider-parameterized positions
├── story_engine.py                 # Instagram Story frame generation engine
├── story_themes.py                 # Theme definitions for Just Dropped stories
├── shared.py                       # Shared utilities (image picker, background removal, etc.)
├── sample_products.py              # Sample product library data
├── test_story_sample.py            # Test script for story generation
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker build file (for App Runner or local Docker)
├── userdata.sh                     # EC2 user data script for automated setup
├── Fonts/
│   ├── EmberModernDisplay/         # Bold, BoldItalic, Italic, Regular (.otf)
│   └── EmberModernText/            # Bold, BoldItalic, Italic, Regular (.otf)
└── pages/
    ├── 1_ILM_Banner_Generator.py       # US banner generator page
    ├── 2_Just_Dropped_Generator.py     # Story frame generator (full wizard)
    ├── 3_ILM_Banner_Generator_CA.py    # Canada banner generator page
    ├── 4_ILM_Banner_Sliders.py         # Slider-based banner generator (1 or 2 products)
    └── 5_Just_Dropped_Simulator.py     # Quick story frame simulator with effects
```

---

## Prerequisites

- **Python 3.11** (required — tested with 3.11.14)
- **pip** (Python package manager)
- **git** (to clone the repo)
- **~8 GB disk space** for Python dependencies (PyTorch + InSPyReNet model are ~6 GB)
- **At least 8 GB RAM** recommended (16 GB preferred — the background removal model uses ~7 GB when loaded)

---

## Option A: Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/awictor/ilm-banner-generator.git
cd ilm-banner-generator
```

### 2. Install Python dependencies

```bash
pip3.11 install -r requirements.txt
```

The `requirements.txt` contains:
```
streamlit==1.41.1
Pillow==11.1.0
numpy==2.2.3
requests==2.32.3
duckduckgo-search==7.3.2
transparent-background
openpyxl==3.1.5
```

Note: `transparent-background` will pull in PyTorch, torchvision, onnxruntime, opencv, scikit-image, scipy, and other heavy dependencies automatically. This is the bulk of the ~8 GB install.

### 3. Run the app

```bash
python3.11 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
```

The app will be available at `http://localhost:8501`.

### 4. (Optional) Set environment variables

```bash
export BRAVE_API_KEY="your-brave-api-key"   # For web search features
export APP_PASSWORD="your-password"          # To enable the password gate
```

---

## Option B: AWS EC2 Deployment

### 1. Launch an EC2 instance

- **AMI**: Amazon Linux 2023 (x86_64)
- **Instance type**: `c5.2xlarge` (8 vCPU, 16 GB RAM) — recommended minimum for background removal
  - Smaller instances (e.g., `c5.xlarge` with 8 GB RAM) will work but may be tight when running background removal
- **Storage**: 20 GB gp3 EBS volume (minimum)
- **Key pair**: Create or select an existing key pair for SSH access
- **Security group**: See [Security Group Configuration](#security-group-configuration)
- **IAM role**: Attach a role with SSM permissions if you want to manage via Systems Manager

### 2. Automated setup via User Data

When launching the instance, paste this into the **User Data** field (or use the included `userdata.sh`):

```bash
#!/bin/bash
set -ex
exec > /var/log/userdata.log 2>&1

# Install system packages
dnf install -y python3.11 python3.11-pip git

# Clone the repo
cd /home/ec2-user
git clone https://github.com/awictor/ilm-banner-generator.git
cd ilm-banner-generator

# Install Python dependencies (includes transparent-background, openpyxl, etc.)
pip3.11 install -r requirements.txt

# Create systemd service
cat > /etc/systemd/system/streamlit.service <<'SVC'
[Unit]
Description=ILM Tools – Streamlit Multi-Page App
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/ilm-banner-generator
EnvironmentFile=-/home/ec2-user/.env
ExecStart=/usr/bin/python3.11 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable streamlit
systemctl start streamlit
```

### 3. Manual setup (if not using User Data)

SSH into the instance and run:

```bash
# Install system packages
sudo dnf install -y python3.11 python3.11-pip git

# Clone the repo
cd /home/ec2-user
git clone https://github.com/awictor/ilm-banner-generator.git
cd ilm-banner-generator

# Install Python dependencies
pip3.11 install -r requirements.txt

# Copy the systemd service file
sudo cp userdata.sh /tmp/  # or create the service manually:
sudo tee /etc/systemd/system/streamlit.service <<'SVC'
[Unit]
Description=ILM Tools – Streamlit Multi-Page App
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/ilm-banner-generator
EnvironmentFile=-/home/ec2-user/.env
ExecStart=/usr/bin/python3.11 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SVC

# Start the service
sudo systemctl daemon-reload
sudo systemctl enable streamlit
sudo systemctl start streamlit
```

### 4. (Optional) Set environment variables

Create `/home/ec2-user/.env`:
```
BRAVE_API_KEY=your-brave-api-key
APP_PASSWORD=your-password
```

Or add them directly to the systemd service file under `[Service]`:
```
Environment=BRAVE_API_KEY=your-key
Environment=APP_PASSWORD=your-password
```

Then restart: `sudo systemctl restart streamlit`

### 5. Access the app

Navigate to `http://<your-ec2-public-ip>:8501`

---

## Option C: Docker

### 1. Build the image

```bash
cd ilm-banner-generator
docker build -t ilm-banner-generator .
```

### 2. Run the container

```bash
docker run -d -p 8501:8080 \
  -e BRAVE_API_KEY="your-key" \
  -e APP_PASSWORD="your-password" \
  ilm-banner-generator
```

Note: The Dockerfile exposes port **8080** internally. Map it to whatever external port you prefer.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BRAVE_API_KEY` | No | Brave Search API key for web search features in the app |
| `APP_PASSWORD` | No | If set, enables a password gate on the home page |

---

## S3 Buckets

Two S3 buckets exist in the AWS account (us-east-1):

| Bucket | Contents | Purpose |
|---|---|---|
| `ilm-banner-deploy-542774802318` | `ilm-deploy.zip` (913 KB) | Original deployment bundle (older version of app + fonts) |
| `ilm-banner-temp-542774802318` | `sample4.tar.gz` (9.1 MB) | Sample output images (story frames) for reference |

These are not required to run the app — they're historical artifacts. The app runs entirely from the git repo.

---

## Security Group Configuration

The production security group (`ilm-banner-sg`, `sg-0da2049ca056c4996`) has these inbound rules:

| Port | Protocol | Source | Description |
|---|---|---|---|
| 22 | TCP | Specific IPs | SSH access (EC2 Instance Connect + admin IP) |
| 8501 | TCP | Whitelisted CIDRs | Streamlit app access (team members only) |

To create a similar security group:

```bash
# Create security group
aws ec2 create-security-group \
  --group-name ilm-banner-sg \
  --description "ILM Banner Generator access" \
  --region us-east-1

# Allow SSH from your IP
aws ec2 authorize-security-group-ingress \
  --group-name ilm-banner-sg \
  --protocol tcp --port 22 \
  --cidr YOUR_IP/32 \
  --region us-east-1

# Allow Streamlit from your IP
aws ec2 authorize-security-group-ingress \
  --group-name ilm-banner-sg \
  --protocol tcp --port 8501 \
  --cidr YOUR_IP/32 \
  --region us-east-1
```

---

## Deploying Code Updates

The current workflow for deploying updates to the production EC2 instance:

### 1. Push changes to GitHub

```bash
cd ilm-banner-generator
git add <files>
git commit -m "Description of changes"
git push
```

### 2. Deploy to EC2 via SSM

```bash
aws ssm send-command \
  --region us-east-1 \
  --instance-ids i-0d81dd77a33cc6c92 \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["export HOME=/root && git config --global --add safe.directory /home/ec2-user/ilm-banner-generator && cd /home/ec2-user/ilm-banner-generator && git pull && sudo systemctl restart streamlit && echo DEPLOY_SUCCESS"]'
```

### 3. Check deployment status

```bash
aws ssm get-command-invocation \
  --region us-east-1 \
  --command-id <command-id-from-step-2> \
  --instance-id i-0d81dd77a33cc6c92
```

### Alternative: Deploy via SSH

```bash
ssh -i ilm-banner-key.pem ec2-user@54.242.127.232
cd /home/ec2-user/ilm-banner-generator
git pull
sudo systemctl restart streamlit
```

---

## Troubleshooting

### Streamlit won't start
```bash
sudo systemctl status streamlit -l
sudo journalctl -u streamlit --no-pager -n 50
```

### Out of memory (background removal)
The InSPyReNet model loads ~7 GB into RAM. If the instance runs out of memory:
- Upgrade to a larger instance type
- Or reduce `max_dim` in `shared.py` (currently set to 512)

### "Tried to use SessionInfo before it was initialized"
This Streamlit error occurs if session state is accessed before the runtime is ready. Ensure `st.session_state` initialization happens at the top of each page, before any widgets that reference it.

### PyTorch `torch.classes` warning
```
Examining the path of torch.classes raised: Tried to instantiate class '__path__._path'
```
This is a harmless warning from PyTorch/transparent-background. It does not affect functionality.

### Git "dubious ownership" error on EC2
When deploying via SSM (which runs as root) but the repo is owned by ec2-user:
```bash
export HOME=/root
git config --global --add safe.directory /home/ec2-user/ilm-banner-generator
```

### Service uses too much CPU/memory
Restart the service to release cached model memory:
```bash
sudo systemctl restart streamlit
```

---

## Current Production Details

| Property | Value |
|---|---|
| **Instance ID** | `i-0d81dd77a33cc6c92` |
| **Region** | `us-east-1` |
| **Instance Type** | `c5.2xlarge` (8 vCPU, 16 GB RAM) |
| **AMI** | `ami-0c1fe732b5494dc14` (Amazon Linux 2023) |
| **Public IP** | `54.242.127.232` |
| **App URL** | `http://54.242.127.232:8501` |
| **EBS Volume** | 20 GB gp3 |
| **Security Group** | `ilm-banner-sg` (`sg-0da2049ca056c4996`) |
| **Key Pair** | `ilm-banner-key` |
| **VPC** | `vpc-00d14628b79a307f6` |
| **Subnet** | `subnet-05fdb61111f7de904` |
| **Python Version** | 3.11.14 |
| **Streamlit Version** | 1.41.1 |
| **Repo Path on Instance** | `/home/ec2-user/ilm-banner-generator` |
| **GitHub Repo** | `https://github.com/awictor/ilm-banner-generator` |
| **Service Name** | `streamlit.service` |
| **Service File** | `/etc/systemd/system/streamlit.service` |
| **App Disk Size** | ~4 MB (repo only) |
| **Python Env Size** | ~7.3 GB (PyTorch + all deps) |
| **Total Packages** | 71 |

### Installed Python Packages (full freeze)

```
altair==5.5.0
attrs==25.4.0
blinker==1.9.0
cachetools==5.5.2
certifi==2026.1.4
charset-normalizer==3.4.4
click==8.3.1
duckduckgo_search==7.3.2
easydict==1.13
flatbuffers==25.12.19
gitdb==4.0.12
GitPython==3.1.46
idna==3.11
ImageIO==2.37.2
Jinja2==3.1.6
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
lazy_loader==0.4
llvmlite==0.46.0
lxml==6.0.2
markdown-it-py==4.0.0
MarkupSafe==3.0.3
mdurl==0.1.2
mpmath==1.3.0
narwhals==2.16.0
networkx==3.6.1
numba==0.64.0
numpy==2.2.3
nvidia-cusparselt-cu12==0.7.1
onnxruntime==1.24.1
opencv-python-headless==4.13.0.92
packaging==24.2
pandas==2.3.3
pillow==11.1.0
platformdirs==4.9.2
pooch==1.9.0
primp==1.0.0
protobuf==5.29.6
pyarrow==23.0.1
pydeck==0.9.1
Pygments==2.19.2
PyMatting==1.1.15
python-dateutil==2.9.0.post0
pytz==2025.2
referencing==0.37.0
rembg==2.0.57
requests==2.32.3
rich==13.9.4
rpds-py==0.30.0
scikit-image==0.26.0
scipy==1.17.0
simsimd==6.5.13
six==1.17.0
smmap==5.0.2
streamlit==1.41.1
sympy==1.14.0
tenacity==9.1.4
tifffile==2026.2.16
toml==0.10.2
tornado==6.5.4
tqdm==4.67.3
typing-inspection==0.4.2
typing_extensions==4.15.0
tzdata==2025.3
urllib3==2.6.3
watchdog==6.0.0
wget==3.2
```
