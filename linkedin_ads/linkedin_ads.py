import json
import os
import secrets
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI")
SCOPES = "r_ads r_ads_reporting rw_ads r_organization_admin r_organization_social"
OAUTH_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
OAUTH_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
BASE_URL = "https://api.linkedin.com/rest/"
API_VERSION = "202604"
MAX_RETRIES = 3
TOKEN_FILE = Path(__file__).parent / "token.json"


# --- Token utilities ---

def extract_code_from_url(redirect_url: str) -> str:
    parsed = urllib.parse.urlparse(redirect_url)
    params = urllib.parse.parse_qs(parsed.query)
    if "code" not in params:
        raise ValueError("No 'code' parameter found in URL")
    return params["code"][0]


def is_token_expired(token: dict) -> bool:
    expires_in = token.get("expires_in", 0)
    obtained_at = token.get("obtained_at", 0)
    return time.time() > obtained_at + expires_in - 60


def extract_id(value) -> str:
    if isinstance(value, dict):
        value = value.get("id", "")
    value = str(value)
    if ":" in value:
        return value.split(":")[-1]
    return value


def save_token(token: dict) -> None:
    TOKEN_FILE.write_text(json.dumps(token, indent=2))


def load_token() -> dict | None:
    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(TOKEN_FILE.read_text())
    except (json.JSONDecodeError, ValueError):
        print("Warning: token.json is corrupt, re-running auth flow...")
        return None


def _exchange_code(code: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    resp = requests.post(OAUTH_TOKEN_URL, data=data)
    resp.raise_for_status()
    token = resp.json()
    token["obtained_at"] = int(time.time())
    return token


def _refresh_token(refresh_token: str) -> dict:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    resp = requests.post(OAUTH_TOKEN_URL, data=data)
    resp.raise_for_status()
    token = resp.json()
    token["obtained_at"] = int(time.time())
    return token


def _run_full_auth_flow() -> dict:
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    }
    auth_url = f"{OAUTH_AUTH_URL}?{urllib.parse.urlencode(params)}"
    print(f"\nOpen this URL in your browser:\n{auth_url}\n")
    redirect_url = input("Paste the full redirect URL here: ").strip()
    code = extract_code_from_url(redirect_url)
    print("Exchanging code for token...")
    token = _exchange_code(code)
    save_token(token)
    print("Token saved to token.json")
    return token


def get_valid_token() -> str:
    token = load_token()
    if token is None:
        print("No token found. Starting OAuth flow...")
        token = _run_full_auth_flow()
        return token["access_token"]

    if is_token_expired(token):
        if "refresh_token" in token:
            print("Access token expired, refreshing...")
            try:
                token = _refresh_token(token["refresh_token"])
                save_token(token)
                print("Token refreshed and saved")
                return token["access_token"]
            except Exception as e:
                print(f"Refresh failed: {e}. Re-running full auth flow...")
                TOKEN_FILE.unlink(missing_ok=True)
                token = _run_full_auth_flow()
                return token["access_token"]
        else:
            print("Token expired and no refresh token. Re-running full auth flow...")
            TOKEN_FILE.unlink(missing_ok=True)
            token = _run_full_auth_flow()
            return token["access_token"]

    return token["access_token"]


# --- API client ---

def make_request(method: str, endpoint: str, token: str, params: dict = None, json_data: dict = None) -> dict:
    url = BASE_URL + endpoint
    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.request(method, url, headers=headers, params=params, json=json_data)
            if resp.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    retry_after = resp.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after else 2 ** attempt
                    print(f"  Rate limited (429). Waiting {wait}s before retry {attempt + 1}/{MAX_RETRIES}...")
                    time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            print(f"  HTTP error on {url}: {e}")
            raise
    raise Exception(f"Max retries exceeded for {url}")


def paginate(endpoint: str, token: str, params: dict = None) -> list:
    params = dict(params or {})
    params["count"] = 100
    params["start"] = 0
    all_elements = []
    while True:
        data = make_request("GET", endpoint, token, params=params)
        elements = data.get("elements", [])
        all_elements.extend(elements)
        paging = data.get("paging", {})
        total = paging.get("total", len(all_elements))
        if len(all_elements) >= total or not elements:
            break
        params["start"] += len(elements)
    return all_elements


# --- Data fetchers ---

def fetch_ad_accounts(token: str) -> list:
    print("Fetching ad accounts...")
    params = {
        "q": "search",
        "search.status.values[0]": "ACTIVE",
        "fields": "id,name,status,currency,type",
    }
    accounts = paginate("adAccounts", token, params)
    print(f"  Found {len(accounts)} active ad accounts")
    return accounts


def fetch_campaign_groups(token: str, account_id: str) -> list:
    print(f"  Fetching campaign groups for account {account_id}...")
    account_urn = f"urn:li:sponsoredAccount:{account_id}"
    params = {
        "q": "search",
        "search.account": account_urn,
    }
    groups = paginate("adCampaignGroups", token, params)
    print(f"    Found {len(groups)} campaign groups")
    return groups


def fetch_campaigns(token: str, account_id: str) -> list:
    print(f"  Fetching campaigns for account {account_id}...")
    account_urn = f"urn:li:sponsoredAccount:{account_id}"
    params = {
        "q": "search",
        "search.account.values[0]": account_urn,
    }
    campaigns = paginate("adCampaigns", token, params)
    print(f"    Found {len(campaigns)} campaigns")
    return campaigns


# --- Analytics fetchers ---

CAMPAIGN_ANALYTICS_FIELDS = (
    "impressions,clicks,costInLocalCurrency,externalWebsiteConversions,"
    "costPerClick,clickThroughRate,costPerConversion,pivotValues,dateRange"
)

COMPANY_ENGAGEMENT_FIELDS = "impressions,clicks,costInLocalCurrency,pivotValues"


def _build_date_range_param() -> str:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    return (
        f"(start:(year:{start.year},month:{start.month},day:{start.day}),"
        f"end:(year:{end.year},month:{end.month},day:{end.day}))"
    )


def fetch_campaign_analytics(token: str, campaign_ids: list) -> list:
    print(f"Fetching campaign analytics for {len(campaign_ids)} campaigns...")
    date_range = _build_date_range_param()
    results = []
    for i in range(0, len(campaign_ids), 10):
        batch = campaign_ids[i:i + 10]
        urns = [f"urn:li:sponsoredCampaign:{cid}" for cid in batch]
        campaigns_param = "List(" + ",".join(urns) + ")"
        params = {
            "q": "statistics",
            "pivots": "List(CAMPAIGN)",
            "timeGranularity": "DAILY",
            "dateRange": date_range,
            "campaigns": campaigns_param,
            "fields": CAMPAIGN_ANALYTICS_FIELDS,
        }
        data = make_request("GET", "adAnalytics", token, params=params)
        elements = data.get("elements", [])
        results.extend(elements)
    print(f"  Retrieved {len(results)} analytics records")
    return results


def fetch_company_engagement(token: str, campaign_ids: list) -> list:
    print(f"Fetching company engagement for {len(campaign_ids)} campaigns...")
    results = []
    for i in range(0, len(campaign_ids), 10):
        batch = campaign_ids[i:i + 10]
        urns = [f"urn:li:sponsoredCampaign:{cid}" for cid in batch]
        campaigns_param = "List(" + ",".join(urns) + ")"
        params = {
            "q": "statistics",
            "pivots": "List(COMPANY)",
            "campaigns": campaigns_param,
            "fields": COMPANY_ENGAGEMENT_FIELDS,
        }
        data = make_request("GET", "adAnalytics", token, params=params)
        elements = data.get("elements", [])
        results.extend(elements)
    print(f"  Retrieved {len(results)} company engagement records")
    return results
