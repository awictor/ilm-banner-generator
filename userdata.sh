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

# Create a startup script so it survives reboots
cat > /etc/systemd/system/streamlit.service <<'SVC'
[Unit]
Description=ILM Tools – Streamlit Multi-Page App
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/ilm-banner-generator
Environment=BRAVE_API_KEY=REDACTED_KEY
ExecStart=/usr/bin/python3.11 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable streamlit
systemctl start streamlit
