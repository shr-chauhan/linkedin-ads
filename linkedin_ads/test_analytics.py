import json
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests

API_VERSION = "202604"
BASE_URL = "https://api.linkedin.com/rest/"
ACCOUNT_ID = "514146109"

TOKEN_FILE = Path("token.json")


def load_token():
    return json.loads(TOKEN_FILE.read_text())["access_token"]


def extract_id(value):
    value = str(value)
    return value.split(":")[-1] if ":" in value else value


token = load_token()

headers = {
    "Authorization": f"Bearer {token}",
    "LinkedIn-Version": API_VERSION,
    "X-Restli-Protocol-Version": "2.0.0",
}

account_urn = urllib.parse.quote(
    f"urn:li:sponsoredAccount:{ACCOUNT_ID}",
    safe=""
)

end_dt = datetime.now(timezone.utc)
start_dt = end_dt - timedelta(days=365)

date_range = (
    f"(start:(year:{start_dt.year},month:{start_dt.month},day:{start_dt.day}),"
    f"end:(year:{end_dt.year},month:{end_dt.month},day:{end_dt.day}))"
)

url = (
    f"{BASE_URL}adAnalytics"
    f"?q=analytics"
    f"&pivot=CREATIVE"
    f"&timeGranularity=ALL"
    f"&dateRange={date_range}"
    f"&accounts=List({account_urn})"
    f"&fields="
    f"pivotValues,"
    f"impressions,"
    f"clicks,"
    f"actionClicks,"
    f"totalEngagements,"
    f"costInLocalCurrency"
)

print("\nURL:")
print(url)

resp = requests.get(url, headers=headers)

print("\nSTATUS:", resp.status_code)

if not resp.ok:
    print(resp.text)
    raise SystemExit()

payload = resp.json()

print("\n====================================")
print("RAW ANALYTICS RESPONSE")
print("====================================")

print(json.dumps(payload, indent=2))

print("\n====================================")
print("SUMMARY")
print("====================================")

elements = payload.get("elements", [])

print(f"Rows Returned: {len(elements)}")

for idx, row in enumerate(elements[:20], start=1):
    print(f"\nRow #{idx}")

    pivots = row.get("pivotValues", [])

    print("Pivot Values:")
    print(json.dumps(pivots, indent=2))

    if pivots:
        print("Extracted Creative ID:")
        print(extract_id(pivots[0]))

    print("Metrics:")
    print(json.dumps(row, indent=2))