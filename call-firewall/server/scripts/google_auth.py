"""One-time: obtain a Google refresh token for Contacts + Calendar (read-only).

1. Google Cloud Console -> create project -> enable "People API" and "Google Calendar API".
2. OAuth consent screen: External, add your account as test user.
3. Credentials -> OAuth client ID -> Desktop app -> download JSON as client_secret.json.
4. Run:  python scripts/google_auth.py client_secret.json
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

sys.path.insert(0, ".")
from callfw.google_api import SCOPES  # noqa: E402

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
client = json.load(open(sys.argv[1]))["installed"]
print(f"GOOGLE_CLIENT_ID={client['client_id']}")
print(f"GOOGLE_CLIENT_SECRET={client['client_secret']}")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
