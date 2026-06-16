#!/usr/bin/env python3
# ==============================================================================
# TITAN OMEGA CORE: UNIFIED ADMINISTRATIVE GOOGLE-MICROSOFT HYBRID ENGINE
# Requires: nexus_keys.py (see nexus_keys.py.example), msal, google-genai, requests
# ==============================================================================
import os
import json
import time
import logging
from datetime import datetime, timezone

import requests
from msal import PublicClientApplication
from google import genai
from google.genai import types

import nexus_keys

logging.basicConfig(
    filename=os.path.expanduser("~/master_run.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURATION
# ==============================================================================
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"
MS_SCOPES = ["Mail.ReadWrite", "Files.ReadWrite", "User.Read"]

# 2026 Victoria Region Rates (Wonthaggi/Dalyston area)
VICTORIA_RATES = {
    "combined_m": 160.00,    # Materials $95/m + Labour $65/m
    "delivery_base": 79.50,  # Regional delivery anchor
    "incentive_margin": 0.15,
}


# ==============================================================================
# LOGISTICS
# ==============================================================================
def get_bin_color_marker() -> str:
    """Returns this week's Bass Coast Shire Zone 2 bin colour."""
    week = datetime.now().isocalendar()[1]
    return "RED week (Landfill + Organics)" if week % 2 == 1 else "YELLOW week (Recycling + Organics)"


def victoria_quote(meters: float) -> float:
    """Returns gross quote total for a given linear metre job."""
    base = meters * VICTORIA_RATES["combined_m"]
    return round((base + VICTORIA_RATES["delivery_base"]) * (1 + VICTORIA_RATES["incentive_margin"]), 2)


# ==============================================================================
# ORCHESTRATOR
# ==============================================================================
class TitanCloudOrchestrator:
    def __init__(self):
        print("=" * 58)
        print("  TITAN OMEGA CORE: ACTIVE CROSS-CLOUD ORCHESTRATOR")
        print("=" * 58)
        self.google_client = None
        self.ms_access_token = None
        self._establish_google()
        self._establish_microsoft()

    # --------------------------------------------------------------------------
    def _establish_google(self):
        """Connect to Google AI Studio via nexus_keys or nexus_creds.json."""
        api_key = getattr(nexus_keys, "GEMINI", None) or os.environ.get("GEMINI_API_KEY")

        if not api_key:
            creds_path = os.path.expanduser("~/nexus_creds.json")
            if os.path.exists(creds_path):
                try:
                    with open(creds_path) as f:
                        data = json.load(f)
                    if data.get("type") == "service_account":
                        self.google_client = genai.Client(
                            vertex=True, project=data.get("project_id")
                        )
                        print("[+] Google: connected via service account.")
                        log.info("Google connected via service account.")
                        return
                except Exception as exc:
                    log.warning("Failed to load nexus_creds.json: %s", exc)

        if api_key:
            self.google_client = genai.Client(api_key=api_key)
            print("[+] Google: connected via API key.")
            log.info("Google connected via API key.")
        else:
            print("[-] Google: offline — no API key found.")
            log.warning("Google offline: no API key found.")

    # --------------------------------------------------------------------------
    def _establish_microsoft(self):
        """Authenticate with Microsoft via device-flow; cache token on-device."""
        cache_path = getattr(nexus_keys, "MS_TOKEN_CACHE",
                             os.path.expanduser("~/microsoft_token.json"))
        client_id = getattr(nexus_keys, "CLIENT_ID", "")

        if not client_id:
            print("[-] Microsoft: CLIENT_ID not set in nexus_keys.py.")
            log.warning("Microsoft offline: CLIENT_ID missing.")
            return

        app = PublicClientApplication(
            client_id, authority="https://login.microsoftonline.com/common"
        )

        # Try silent refresh from cached token
        if os.path.exists(cache_path):
            try:
                with open(cache_path) as f:
                    cached = json.load(f)
                expires_at = cached.get("expires_at", 0)
                if expires_at > time.time() + 60:
                    self.ms_access_token = cached["access_token"]
                    print("[+] Microsoft: token restored from cache.")
                    log.info("Microsoft token restored from cache.")
                    return
            except Exception as exc:
                log.warning("Cache read failed: %s", exc)

        # Try MSAL silent (uses in-memory account cache on first run)
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(MS_SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self.ms_access_token = result["access_token"]
                self._save_token(result, cache_path)
                print("[+] Microsoft: token refreshed silently.")
                log.info("Microsoft token refreshed silently.")
                return

        # Interactive device-flow login
        try:
            flow = app.initiate_device_flow(scopes=MS_SCOPES)
            if "user_code" not in flow:
                print("[-] Microsoft: device flow initiation failed.")
                log.error("Microsoft device flow failed: %s", flow)
                return

            print("\n========== ACTION REQUIRED ==========")
            print(f"Visit: {flow['verification_uri']}")
            print(f"Code:  {flow['user_code']}")
            print("=====================================\n")

            result = app.acquire_token_by_device_flow(flow)
            if "access_token" in result:
                self.ms_access_token = result["access_token"]
                self._save_token(result, cache_path)
                print("[+] Microsoft: authenticated successfully.")
                log.info("Microsoft authenticated via device flow.")
            else:
                print(f"[-] Microsoft: auth failed — {result.get('error_description', 'unknown')}")
                log.error("Microsoft auth error: %s", result)
        except Exception as exc:
            print(f"[-] Microsoft: connection error — {exc}")
            log.error("Microsoft connection error: %s", exc)

    @staticmethod
    def _save_token(result: dict, path: str):
        result["expires_at"] = time.time() + result.get("expires_in", 3600)
        try:
            with open(path, "w") as f:
                json.dump(result, f)
        except Exception as exc:
            log.warning("Failed to save token cache: %s", exc)

    # --------------------------------------------------------------------------
    def query_grounded_intelligence(self, subject: str, body: str) -> str:
        """Send email details to Gemini with Google Search grounding."""
        if not self.google_client:
            return "Google Cloud Engine offline."

        system_rules = (
            "You are the Titan Omega business engine for Gunn for Hire, a construction company "
            "in Dalyston, Victoria. Formulate a professional, high-value commercial response "
            "using current real estate parameters, compliance standards, or quotes. "
            "Ground responses with live web search where relevant."
        )
        prompt = (
            f"Analyse this incoming email and draft an optimised reply.\n"
            f"Subject: {subject}\n"
            f"Body preview: {body}"
        )
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_rules,
                temperature=0.2,
                tools=[{"google_search": {}}],
            )
            response = self.google_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as exc:
            log.error("Gemini inference error: %s", exc)
            return f"Gemini error: {exc}"

    # --------------------------------------------------------------------------
    def run_office_sync_loop(self):
        """Fetch unread Outlook emails and generate AI responses."""
        if not self.ms_access_token:
            print("[-] Microsoft sync offline — authenticate first.")
            return

        headers = {"Authorization": f"Bearer {self.ms_access_token}"}
        url = f"{GRAPH_ENDPOINT}/me/messages?$filter=isRead eq false&$top=5"

        try:
            res = requests.get(url, headers=headers, timeout=15)
            res.raise_for_status()
        except requests.RequestException as exc:
            print(f"[-] Office sync failed: {exc}")
            log.error("Office sync error: %s", exc)
            return

        emails = res.json().get("value", [])
        print(f"[*] {len(emails)} unread message(s) found.")
        log.info("%d unread messages.", len(emails))

        for mail in emails:
            subject = mail.get("subject", "Business Enquiry")
            preview = mail.get("bodyPreview", "")
            print(f"\n[*] Processing: '{subject}'")
            reply = self.query_grounded_intelligence(subject, preview)
            log.info("Processed: %s", subject)
            print("\n========== TITAN RESPONSE ==========")
            print(reply)
            print("=====================================\n")


# ==============================================================================
# EXECUTION
# ==============================================================================
def execute_system_runtime():
    orchestrator = TitanCloudOrchestrator()
    orchestrator.run_office_sync_loop()

    print(f"[*] Bin schedule: {get_bin_color_marker()}")

    for meters in [10, 20, 30, 50]:
        total = victoria_quote(meters)
        print(f"[*] Quote {meters}m = ${total:,.2f} AUD")


if __name__ == "__main__":
    execute_system_runtime()
