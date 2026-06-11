import json
import urllib.parse
from pathlib import Path

import requests

API_VERSION = "202604"
BASE_URL = "https://api.linkedin.com/rest/"
TOKEN_FILE = Path("token.json")

def load_token():
    return json.loads(TOKEN_FILE.read_text())["access_token"]

token = load_token()

headers = {
    "Authorization": f"Bearer {token}",
    "LinkedIn-Version": API_VERSION,
    "X-Restli-Protocol-Version": "2.0.0",
}

skills = [
    "urn:li:skill:8462",
    "urn:li:skill:11979",
    "urn:li:skill:12772",
    "urn:li:skill:1417",
    "urn:li:skill:1631"
]

# IMPORTANT:
# Encode each URN individually, not the entire List(...)
encoded_skills = [
    urllib.parse.quote(skill, safe="")
    for skill in skills
]

urn_param = f"List({','.join(encoded_skills)})"

url = (
    f"{BASE_URL}adTargetingEntities"
    f"?q=urns"
    f"&queryVersion=QUERY_USES_URNS"
    f"&urns={urn_param}"
)

print("Request URL:")
print(url)

resp = requests.get(url, headers=headers)

output = {
    "status_code": resp.status_code,
    "request_url": url,
}

try:
    output["response"] = resp.json()
except Exception:
    output["response"] = resp.text

with open("multiple_skills_lookup.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

print(f"\nStatus: {resp.status_code}")
print("Written: multiple_skills_lookup.json")

if resp.ok:
    elements = output["response"].get("elements", [])

    print(f"Resolved {len(elements)} skills")

    for element in elements:
        print(
            f"{element.get('urn')} -> {element.get('name')}"
        )