#!/usr/bin/env bash
set -euo pipefail

echo "====================================================="
echo "   🚀 CBR Currency Terminal - Auto Deployment Script "
echo "====================================================="

# Ensure curl is installed
if ! command -v curl &> /dev/null; then
    echo "[*] Installing curl..."
    apt-get update -qq && apt-get install -y curl
fi

# 1. Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "[*] Docker not found. Installing Docker automatically..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm -f get-docker.sh
    systemctl enable --now docker
else
    echo "[✓] Docker is already installed."
fi

# 2. Ensure docker compose plugin is available
if ! docker compose version &> /dev/null; then
    echo "[*] Installing docker compose plugin..."
    apt-get update -qq && apt-get install -y docker-compose-plugin
fi

# 3. Ensure data directory exists
mkdir -p data

# 4. Build and launch container in background
echo "[*] Building and starting the container..."
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d --build

# 5. Retrieve Public IP
SERVER_IP=$(curl -s --max-time 4 https://api.ipify.org || curl -s --max-time 4 https://ifconfig.me || echo "YOUR_SERVER_IP")

echo ""
echo "====================================================="
echo " ✅ Application successfully launched!"
echo " 🌐 Access your dashboard at:"
echo "    http://${SERVER_IP}:8050"
echo "====================================================="
echo " Tip: The scheduler runs daily at 18:15 Moscow time."
echo " To view live logs: docker compose logs -f"
echo "====================================================="
