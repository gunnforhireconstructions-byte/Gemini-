#!/data/data/com.termux/files/usr/bin/bash
while true; do
    echo "[*] SYNC: Pushing secured scripts..."
    git add .
    git commit -m "Titan Omega: Secured Sync $(date)" 2>/dev/null
    git push origin main

    # Restart master_run.py inside tmux if the session has died
    if ! tmux has-session -t titan 2>/dev/null; then
        echo "[!] Titan session down. Restarting..."
        tmux new-session -d -s titan "python3 ~/master_run.py"
    fi

    sleep 600
done
