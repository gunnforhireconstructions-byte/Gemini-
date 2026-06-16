#!/bin/bash
# =============================================================================
# TITAN OMEGA — ADB DEPLOYMENT SCRIPT
# Run this on your PC with the phone connected via USB (ADB debugging enabled)
# =============================================================================
set -e

PHONE_HOME="/data/data/com.termux/files/home"
SDCARD="/sdcard/titan_deploy"
TERMUX_PKG="$PHONE_HOME/usr/bin/pkg"

echo "=================================================="
echo "  TITAN OMEGA: ADB DEPLOYMENT"
echo "=================================================="

# Verify ADB connection
echo "[*] Checking ADB connection..."
adb wait-for-device
DEVICE=$(adb devices | grep -v "List" | grep "device$" | awk '{print $1}')
if [ -z "$DEVICE" ]; then
    echo "[!] No device found. Check USB connection and enable ADB debugging."
    exit 1
fi
echo "[+] Connected: $DEVICE"

# Push scripts to shared storage (no root needed)
echo "[*] Pushing files to phone..."
adb shell "mkdir -p $SDCARD"
adb push master_run.py   "$SDCARD/master_run.py"
adb push setup_termux.sh "$SDCARD/setup_termux.sh"

# If nexus_keys.py exists locally, push it too
if [ -f "nexus_keys.py" ]; then
    adb push nexus_keys.py "$SDCARD/nexus_keys.py"
    echo "[+] nexus_keys.py pushed."
fi

# If nexus_creds.json exists locally, push it too
if [ -f "nexus_creds.json" ]; then
    adb push nexus_creds.json "$SDCARD/nexus_creds.json"
    echo "[+] nexus_creds.json pushed."
fi

echo "[+] Files pushed to $SDCARD"

# Copy from shared storage into Termux home via Termux RUN_COMMAND broadcast
echo "[*] Installing files into Termux home..."
adb shell "am broadcast --user 0 \
  -a com.termux.RUN_COMMAND \
  --es com.termux.RUN_COMMAND_PATH '/data/data/com.termux/files/usr/bin/bash' \
  --esa 'com.termux.RUN_COMMAND_ARGUMENTS,-c,cp $SDCARD/master_run.py ~/master_run.py && chmod +x ~/master_run.py' \
  --ez com.termux.RUN_COMMAND_BACKGROUND true \
  -n com.termux/com.termux.app.RunCommandService" 2>/dev/null || {
    echo "[!] Termux broadcast failed — open Termux and run manually:"
    echo "    cp $SDCARD/master_run.py ~/master_run.py"
}

sleep 2

# Install Python dependencies
echo "[*] Installing Python dependencies on phone..."
adb shell "am broadcast --user 0 \
  -a com.termux.RUN_COMMAND \
  --es com.termux.RUN_COMMAND_PATH '/data/data/com.termux/files/usr/bin/bash' \
  --esa 'com.termux.RUN_COMMAND_ARGUMENTS,-c,pkg install -y python python-cryptography termux-api tmux 2>&1 | tee ~/deploy.log' \
  --ez com.termux.RUN_COMMAND_BACKGROUND false \
  -n com.termux/com.termux.app.RunCommandService" 2>/dev/null

adb shell "am broadcast --user 0 \
  -a com.termux.RUN_COMMAND \
  --es com.termux.RUN_COMMAND_PATH '/data/data/com.termux/files/usr/bin/bash' \
  --esa 'com.termux.RUN_COMMAND_ARGUMENTS,-c,pip install msal requests google-genai gspread 2>&1 | tee -a ~/deploy.log' \
  --ez com.termux.RUN_COMMAND_BACKGROUND false \
  -n com.termux/com.termux.app.RunCommandService" 2>/dev/null

# Kill any existing titan tmux session
echo "[*] Stopping any existing Titan session..."
adb shell "am broadcast --user 0 \
  -a com.termux.RUN_COMMAND \
  --es com.termux.RUN_COMMAND_PATH '/data/data/com.termux/files/usr/bin/bash' \
  --esa 'com.termux.RUN_COMMAND_ARGUMENTS,-c,tmux kill-session -t titan 2>/dev/null; true' \
  --ez com.termux.RUN_COMMAND_BACKGROUND true \
  -n com.termux/com.termux.app.RunCommandService" 2>/dev/null

sleep 2

# Launch Titan Omega in a detached tmux session
echo "[*] Launching Titan Omega..."
adb shell "am broadcast --user 0 \
  -a com.termux.RUN_COMMAND \
  --es com.termux.RUN_COMMAND_PATH '/data/data/com.termux/files/usr/bin/bash' \
  --esa 'com.termux.RUN_COMMAND_ARGUMENTS,-c,tmux new-session -d -s titan python3 ~/master_run.py' \
  --ez com.termux.RUN_COMMAND_BACKGROUND true \
  -n com.termux/com.termux.app.RunCommandService" 2>/dev/null

sleep 3

echo ""
echo "=================================================="
echo "  [+] DEPLOYMENT COMPLETE"
echo "  Run: bash adb_monitor.sh    — live log stream"
echo "  Run: python3 pc_interface.py — full dashboard"
echo "=================================================="
