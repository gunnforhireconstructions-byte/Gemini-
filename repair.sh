#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
# TITAN OMEGA — ONE-RUN REPAIR SCRIPT
# Run this once on Termux to fix git auth, kill the old watchdog, and switch
# to the correct branch with all Android optimisations.
# Usage: bash repair.sh
# =============================================================================

echo "=================================================="
echo "  TITAN OMEGA: REPAIR"
echo "=================================================="

# 1. Kill runaway old watchdog and any stale titan sessions
echo "[*] Killing old processes..."
pkill -f bridge_guardian.sh 2>/dev/null && echo "[+] bridge_guardian.sh stopped." || echo "[-] No bridge_guardian.sh found."
pkill -f titan_omega.py     2>/dev/null && echo "[+] titan_omega.py stopped."     || echo "[-] No titan_omega.py found."
tmux kill-session -t titan  2>/dev/null && echo "[+] tmux titan session killed."  || echo "[-] No titan tmux session."

# 2. Configure git identity
echo ""
echo "[*] Configuring git identity..."
git config --global user.email "Gunnforhireconstructions@gmail.com"
git config --global user.name  "Gunn for Hire"
echo "[+] Git identity set."

# 3. Set GitHub PAT for HTTPS push
echo ""
echo "[*] GitHub authentication setup"
echo "    You need a Personal Access Token (PAT) with 'repo' scope."
echo "    Create one at: https://github.com/settings/tokens"
echo ""
printf "Paste your GitHub PAT and press Enter: "
read -r PAT

if [ -z "$PAT" ]; then
    echo "[!] No token entered — skipping remote URL update."
    echo "    You can set it later: git remote set-url origin https://gunnforhireconstructions-byte:<PAT>@github.com/gunnforhireconstructions-byte/Gemini-.git"
else
    git remote set-url origin "https://gunnforhireconstructions-byte:${PAT}@github.com/gunnforhireconstructions-byte/Gemini-.git"
    echo "[+] Remote URL updated with PAT."
fi

# 4. Switch to the correct branch (all Android optimisations)
echo ""
echo "[*] Switching to the optimised branch..."
git fetch origin claude/command-package-mappings-g7u0ff 2>&1
git checkout -B claude/command-package-mappings-g7u0ff origin/claude/command-package-mappings-g7u0ff
echo "[+] Now on branch: $(git branch --show-current)"

echo ""
echo "=================================================="
echo "  [+] REPAIR COMPLETE"
echo ""
echo "  Next steps:"
echo "  1. Copy your nexus_keys.py to ~/nexus_keys.py"
echo "  2. Copy your nexus_creds.json to ~/nexus_creds.json"
echo "  3. Run: bash setup_termux.sh   (install deps)"
echo "  4. Run: tmux new-session -d -s titan 'python3 ~/master_run.py'"
echo "  5. Run: python3 pc_interface.py  (local dashboard)"
echo "=================================================="
