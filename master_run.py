#!/usr/bin/env python3
# ==============================================================================
# TITAN OMEGA CORE: UNIFIED ADMINISTRATIVE GOOGLE-MICROSOFT HYBRID ENGINE
# Requires: nexus_keys.py (see nexus_keys.py.example)
# Deps: pkg install python python-cryptography termux-api
#       pip install msal requests google-genai gspread
# ==============================================================================
import os
import sys
import json
import time
import signal
import logging
import subprocess
from datetime import datetime
from logging.handlers import RotatingFileHandler

import requests
from msal import PublicClientApplication
from google import genai
from google.genai import types
import gspread
from google.oauth2.service_account import Credentials

import nexus_keys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(
            os.path.expanduser("~/master_run.log"),
            maxBytes=500_000,
            backupCount=1,
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURATION
# ==============================================================================
GRAPH_ENDPOINT  = "https://graph.microsoft.com/v1.0"
MS_SCOPES       = ["Mail.ReadWrite", "Files.ReadWrite", "User.Read"]
SHEET_NAME      = "Gunn for Hire Master Operations"
CREDS_FILE      = os.path.expanduser("~/nexus_creds.json")
RETRY_BASE      = 30
REQUEST_TIMEOUT = 30  # longer timeout for mobile networks

VICTORIA_RATES = {
    "combined_m": 160.00,
    "delivery_base": 79.50,
    "incentive_margin": 0.15,
}

GSHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ==============================================================================
# ANDROID / TERMUX HELPERS
# ==============================================================================
def _termux(cmd: list):
    """Fire-and-forget a termux-* command. Silently ignored if not on Termux."""
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass

def speak(text: str):
    _termux(["termux-tts-speak", text])

def notify(title: str, content: str):
    _termux([
        "termux-notification",
        "--title", title,
        "--content", content,
        "--id", "titan_omega",
        "--ongoing",
    ])

def notify_clear():
    _termux(["termux-notification-remove", "titan_omega"])

def vibrate():
    _termux(["termux-vibrate", "-d", "500"])

def wake_lock():
    _termux(["termux-wake-lock"])

def wake_unlock():
    _termux(["termux-wake-unlock"])

def network_up() -> bool:
    """Returns True if we have a live internet connection."""
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except requests.RequestException:
        return False

def poll_interval() -> int:
    """5 min during business hours (7am–7pm), 30 min overnight."""
    return 300 if 7 <= datetime.now().hour < 19 else 1800


# ==============================================================================
# SIGTERM — Android fires this before force-killing the process
# ==============================================================================
def _handle_sigterm(signum, frame):
    log.info("SIGTERM received — shutting down.")
    speak("Titan Omega shutting down.")
    wake_unlock()
    notify_clear()
    sys.exit(0)

signal.signal(signal.SIGTERM, _handle_sigterm)


# ==============================================================================
# UTILITIES
# ==============================================================================
def bin_schedule() -> str:
    week = datetime.now().isocalendar()[1]
    return "RED (Landfill + Organics)" if week % 2 == 1 else "YELLOW (Recycling + Organics)"

def victoria_quote(meters: float) -> float:
    base = meters * VICTORIA_RATES["combined_m"]
    return round((base + VICTORIA_RATES["delivery_base"]) * (1 + VICTORIA_RATES["incentive_margin"]), 2)

def backoff(failures: int) -> int:
    return min(RETRY_BASE * (2 ** min(failures, 5)), 600)


# ==============================================================================
# GOOGLE SHEETS LOGGING
# ==============================================================================
def connect_sheets():
    if not os.path.exists(CREDS_FILE):
        log.warning("Sheets: %s not found — logging disabled.", CREDS_FILE)
        return None
    try:
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=GSHEETS_SCOPES)
        sheet = gspread.authorize(creds).open(SHEET_NAME).sheet1
        log.info("Google Sheets: connected to '%s'.", SHEET_NAME)
        return sheet
    except Exception as e:
        log.error("Sheets connect failed: %s", e)
        return None

def log_to_sheet(sheet, subject: str, preview: str, reply: str, status: str = "Processed"):
    if not sheet:
        return
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row(
            [ts, subject, preview[:300], reply[:1000], status],
            value_input_option="USER_ENTERED",
        )
        log.info("Sheets: logged '%s'.", subject)
    except Exception as e:
        log.error("Sheets write failed: %s", e)

def log_quote_to_sheet(sheet, meters: float, total: float):
    if not sheet:
        return
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row(
            [ts, f"Quote: {meters}m", "", f"${total:,.2f} AUD", "Quote"],
            value_input_option="USER_ENTERED",
        )
    except Exception as e:
        log.error("Sheets quote write failed: %s", e)


# ==============================================================================
# GOOGLE GEMINI
# ==============================================================================
def connect_google():
    api_key = getattr(nexus_keys, "GEMINI", None) or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.warning("Gemini key not set — AI replies disabled.")
        return None
    try:
        client = genai.Client(api_key=api_key)
        log.info("Google AI: connected.")
        return client
    except Exception as e:
        log.error("Google connect failed: %s", e)
        return None

def gemini_reply(client, subject: str, body: str) -> str:
    if not client:
        return "[Google offline — no reply generated]"
    try:
        cfg = types.GenerateContentConfig(
            system_instruction=(
                "You are the Titan Omega engine for Gunn for Hire, a construction business "
                "in Dalyston, Victoria. Write a concise, professional, commercial reply."
            ),
            temperature=0.2,
            tools=[{"google_search": {}}],
        )
        r = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Subject: {subject}\nBody preview: {body}",
            config=cfg,
        )
        return r.text
    except Exception as e:
        log.error("Gemini error: %s", e)
        return f"Gemini error: {e}"


# ==============================================================================
# MICROSOFT
# ==============================================================================
def _msal_app():
    return PublicClientApplication(
        getattr(nexus_keys, "CLIENT_ID", ""),
        authority="https://login.microsoftonline.com/common",
    )

def _save_token(token: dict):
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    cache_path = getattr(nexus_keys, "MS_TOKEN_CACHE", os.path.expanduser("~/microsoft_token.json"))
    try:
        with open(cache_path, "w") as f:
            json.dump(token, f)
    except Exception as e:
        log.warning("Token save failed: %s", e)

def get_ms_token() -> str | None:
    cache_path = getattr(nexus_keys, "MS_TOKEN_CACHE", os.path.expanduser("~/microsoft_token.json"))

    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                cached = json.load(f)
            if cached.get("expires_at", 0) > time.time() + 120:
                return cached["access_token"]
        except Exception as e:
            log.warning("Cache read error: %s", e)

    app = _msal_app()
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(MS_SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_token(result)
            log.info("MS token silently refreshed.")
            return result["access_token"]

    flow = app.initiate_device_flow(scopes=MS_SCOPES)
    if "user_code" not in flow:
        log.error("Device flow init failed: %s", flow)
        return None

    print("\n========== MICROSOFT LOGIN REQUIRED ==========")
    print(f"  Visit:  {flow['verification_uri']}")
    print(f"  Code:   {flow['user_code']}")
    print("==============================================\n")
    speak(f"Microsoft login required. Visit the website and enter code {' '.join(flow['user_code'])}")
    notify("Titan Omega", f"Microsoft login needed. Code: {flow['user_code']}")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        _save_token(result)
        log.info("MS device-flow login successful.")
        return result["access_token"]

    log.error("MS auth failed: %s", result.get("error_description", "unknown"))
    return None

def fetch_emails(token: str) -> list:
    r = requests.get(
        f"{GRAPH_ENDPOINT}/me/messages?$filter=isRead eq false&$top=5",
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("value", [])


# ==============================================================================
# MAIN LOOP — optimised for Android/Termux
# ==============================================================================
def main():
    print("=" * 58)
    print("   TITAN OMEGA CORE — LIVE CROSS-CLOUD ENGINE ONLINE")
    print("=" * 58)
    log.info("Titan Omega starting.")

    wake_lock()
    speak("Titan Omega online. Cross-cloud engine active.")
    notify("Titan Omega", "Engine online.")

    bin_msg = f"Bin schedule: {bin_schedule()}"
    print(f"[*] {bin_msg}")
    speak(bin_msg)

    for m in [10, 20, 30, 50]:
        print(f"[*] Quote {m}m = ${victoria_quote(m):,.2f} AUD")
    print()

    google   = connect_google()
    sheet    = connect_sheets()
    failures = 0

    for m in [10, 20, 30, 50]:
        log_quote_to_sheet(sheet, m, victoria_quote(m))

    while True:
        try:
            # Network check — wait silently without burning the retry counter
            if not network_up():
                log.warning("No network — waiting 30s.")
                time.sleep(30)
                continue

            if not google:
                google = connect_google()

            token = get_ms_token()
            if not token:
                wait = backoff(failures)
                log.warning("No MS token — retrying in %ds.", wait)
                speak(f"No Microsoft token. Retrying in {wait} seconds.")
                time.sleep(wait)
                failures += 1
                continue

            failures = 0
            emails = fetch_emails(token)
            log.info("%d unread email(s).", len(emails))

            ts_str = datetime.now().strftime("%H:%M")

            if emails:
                count = len(emails)
                speak(f"{count} unread email{'s' if count != 1 else ''} found.")
                vibrate()
                notify("Titan Omega", f"{count} new email{'s' if count != 1 else ''} — {ts_str}")
            else:
                speak("No new emails.")
                notify("Titan Omega", f"No new emails. Last checked {ts_str}")

            for mail in emails:
                subject = mail.get("subject", "Enquiry")
                preview = mail.get("bodyPreview", "")
                log.info("Processing: %s", subject)
                speak(f"Processing email: {subject}")

                reply = gemini_reply(google, subject, preview)
                log_to_sheet(sheet, subject, preview, reply)

                print(f"\n{'─' * 54}")
                print(f"  {subject}")
                print(f"{'─' * 54}")
                print(reply)
                speak(reply[:400])

            interval = poll_interval()
            log.info("Sleeping %ds (next poll %s).", interval,
                     "business hours" if interval == 300 else "overnight")
            time.sleep(interval)

        except KeyboardInterrupt:
            log.info("Stopped by user.")
            speak("Titan Omega shutting down.")
            wake_unlock()
            notify_clear()
            print("\n[*] Titan Omega shut down cleanly.")
            break

        except Exception as e:
            wait = backoff(failures)
            log.error("Error: %s — reconnecting in %ds.", e, wait)
            speak(f"Connection error. Reconnecting in {wait} seconds.")
            notify("Titan Omega", f"Error: reconnecting in {wait}s")
            print(f"[!] {e} — reconnecting in {wait}s...")
            time.sleep(wait)
            failures += 1
            google = None
            sheet  = connect_sheets()


if __name__ == "__main__":
    main()
