#!/data/data/com.termux/files/usr/bin/bash
# =========================================================================
# TITAN OMEGA: TERMUX ENVIRONMENT SETUP
# Run once to install all dependencies before launching master_run.py
# =========================================================================
set -e

termux-wake-lock

echo "[*] Updating package index..."
pkg update -y

# python-cryptography must be installed via pkg BEFORE pip.
# pip will try to compile it from source using Rust, which fails on Android.
echo "[*] Installing native Termux packages..."
pkg install -y python python-cryptography openssl cronie

echo "[*] Installing Python libraries..."
pip install msal requests google-genai pyyaml gspread

echo "[*] Creating directory structure..."
mkdir -p ~/core_automation ~/business_vault
chmod 700 ~/core_automation ~/business_vault

echo "[*] Setup complete."
echo "    Next: copy nexus_keys.py.example -> nexus_keys.py and fill in your credentials."
echo "    Then: python3 master_run.py"
