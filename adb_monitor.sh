#!/bin/bash
# =============================================================================
# TITAN OMEGA — LIVE ADB LOG MONITOR
# Streams titan.log from your phone to this terminal in real time.
# Run: bash adb_monitor.sh
# =============================================================================

LOGFILE="/data/data/com.termux/files/home/titan.log"

echo "=================================================="
echo "  TITAN OMEGA: LIVE MONITOR"
echo "  Phone log: $LOGFILE"
echo "  Press Ctrl+C to stop"
echo "=================================================="
echo ""

adb wait-for-device

# Stream the log — shows last 20 lines then follows live
adb shell "tail -n 20 -f $LOGFILE"
