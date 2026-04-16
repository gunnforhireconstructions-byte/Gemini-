import gspread
from google.oauth2.service_account import Credentials
import time, os, requests
import nexus_keys

GEMINI_KEY = nexus_keys.GEMINI
OPENAI_KEY = nexus_keys.OPENAI
CLAUDE_KEY = nexus_keys.CLAUDE
KEY_FILE = os.path.expanduser("~/nexus_creds.json")
SHEET_NAME = "Gunn for Hire Master Operations"

def titan_loop():
    print("--- TITAN OMEGA: SECURE BPC MODE ONLINE ---")
    while True:
        try:
            if not os.path.exists(KEY_FILE):
                print(f"[!] Error: {KEY_FILE} missing."); time.sleep(60); continue
            
            creds = Credentials.from_service_account_file(KEY_FILE, scopes=["https://www.googleapis.com/auth/drive", "https://spreadsheets.google.com/feeds"])
            sheet = gspread.authorize(creds).open(SHEET_NAME).sheet1
            
            for row in sheet.get_all_records():
                if row.get('Status') in ['Open', 'New', 'Urgent']:
                    print(f"[ACTION] Processing Wonthaggi Lead: {row.get('Client/Project')}")
            time.sleep(300)
        except Exception as e:
            print(f"[ENGINE FAULT] {e}"); time.sleep(30)

if __name__ == "__main__":
    titan_loop()
