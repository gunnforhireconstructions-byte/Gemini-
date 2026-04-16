#!/bin/bash
while true; do
    echo "[*] SYNC: Pushing Secured Scripts..."
    git add .
    git commit -m "Titan Omega: Secured Sync $(date)"
    git push origin main --force
    
    if ! pgrep -f "titan_omega.py" > /dev/null; then
        echo "[!] MOTOR DOWN. Restarting Engine..."
        nohup python3 titan_omega.py > titan.log 2>&1 &
    fi
    sleep 600
done
