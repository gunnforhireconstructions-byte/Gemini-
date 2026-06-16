#!/usr/bin/env python3
"""
TITAN OMEGA — PC DASHBOARD
Shows live engine status, recent emails processed, and quote log
pulled from the Google Sheet and phone log via ADB.

Install on PC: pip install gspread google-auth rich
Run:           python3 pc_interface.py
"""

import os
import sys
import time
import subprocess
from datetime import datetime

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("Install rich for the dashboard: pip install rich")
    sys.exit(1)

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_SHEETS = True
except ImportError:
    HAS_SHEETS = False

# ======================== CONFIGURE ========================
CREDS_FILE = os.path.expanduser("~/nexus_creds.json")
SHEET_NAME = "Gunn for Hire Master Operations"
REFRESH    = 15
# ===========================================================

GS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

console = Console()


def adb_status() -> dict:
    result = {"connected": False, "titan_running": False, "last_log": ""}
    try:
        devices = subprocess.check_output(
            ["adb", "devices"], stderr=subprocess.DEVNULL, timeout=5
        ).decode()
        result["connected"] = "device" in devices

        if result["connected"]:
            out = subprocess.check_output(
                ["adb", "shell",
                 "tmux has-session -t titan 2>/dev/null && echo RUNNING || echo STOPPED"],
                stderr=subprocess.DEVNULL, timeout=5,
            ).decode().strip()
            result["titan_running"] = "RUNNING" in out

            last = subprocess.check_output(
                ["adb", "shell",
                 "tail -n 1 /data/data/com.termux/files/home/titan.log 2>/dev/null"],
                stderr=subprocess.DEVNULL, timeout=5,
            ).decode().strip()
            result["last_log"] = last
    except Exception:
        pass
    return result


def fetch_sheet_rows(sheet, count: int = 15) -> list:
    try:
        all_rows = sheet.get_all_values()
        return all_rows[-count:] if len(all_rows) > count else all_rows
    except Exception as e:
        return [["Error reading sheet:", str(e), "", "", ""]]


def connect_sheet():
    if not HAS_SHEETS or not os.path.exists(CREDS_FILE):
        return None
    try:
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=GS_SCOPES)
        return gspread.authorize(creds).open(SHEET_NAME).sheet1
    except Exception:
        return None


def build_dashboard(status: dict, rows: list):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    phone_color = "green" if status["connected"] else "red"
    titan_color = "green" if status["titan_running"] else "red"

    status_text = Text()
    status_text.append("  Phone ADB:    ", style="bold")
    status_text.append(f"{'CONNECTED' if status['connected'] else 'DISCONNECTED'}\n",
                       style=f"bold {phone_color}")
    status_text.append("  Titan Engine: ", style="bold")
    status_text.append(f"{'RUNNING' if status['titan_running'] else 'STOPPED'}\n",
                       style=f"bold {titan_color}")
    status_text.append("  Last log:     ", style="bold")
    status_text.append(f"{status['last_log'][:80]}\n", style="dim")
    status_text.append(f"  Refreshed:    {now}", style="dim")

    status_panel = Panel(status_text,
                         title="[bold cyan]TITAN OMEGA STATUS[/]",
                         border_style="cyan")

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Timestamp", width=19)
    table.add_column("Subject / Event", min_width=25)
    table.add_column("Preview", min_width=20)
    table.add_column("Status", width=12)

    for row in reversed(rows[-15:]):
        if len(row) >= 5:
            ts, subject, preview, _, status_col = row[0], row[1], row[2], row[3], row[4]
        elif len(row) == 4:
            ts, subject, preview, status_col = row[0], row[1], row[2], row[3]
        else:
            continue
        color = {"Replied": "green", "Reply Failed": "red",
                 "Quote": "yellow", "Processed": "blue"}.get(status_col, "white")
        table.add_row(
            ts, subject[:40],
            preview[:35] + "..." if len(preview) > 35 else preview,
            Text(status_col, style=f"bold {color}"),
        )

    activity_panel = Panel(table,
                           title="[bold magenta]RECENT ACTIVITY — Gunn for Hire Master Operations[/]",
                           border_style="magenta")

    from rich.console import Group
    return Group(status_panel, activity_panel)


def main():
    console.print(Panel.fit(
        "[bold cyan]TITAN OMEGA PC DASHBOARD[/]\n[dim]Ctrl+C to exit | refreshes every 15s[/]",
        border_style="cyan"
    ))

    sheet = connect_sheet()
    if not sheet:
        console.print("[yellow]Google Sheet not connected — ADB status only.[/]")
        console.print("[dim]Place nexus_creds.json at ~/nexus_creds.json to enable.[/]\n")

    with Live(console=console, refresh_per_second=0.5, screen=True) as live:
        while True:
            try:
                status = adb_status()
                rows   = fetch_sheet_rows(sheet) if sheet else [["—", "Sheet not connected", "", "", "—"]]
                live.update(build_dashboard(status, rows))
                time.sleep(REFRESH)
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/]")
                time.sleep(5)


if __name__ == "__main__":
    main()
