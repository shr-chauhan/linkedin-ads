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


_http_session = requests.Session()

# --- API client ---

def _build_url(base_url: str, params: dict) -> str:
    safe_chars = "[](),"
    qs = "&".join(
        f"{urllib.parse.quote(str(k), safe=safe_chars)}={urllib.parse.quote(str(v), safe=safe_chars)}"
        for k, v in params.items()
    )
    return f"{base_url}?{qs}"


def make_request(method: str, endpoint: str, token: str, params: dict = None, json_data: dict = None) -> dict:
    base_url = BASE_URL + endpoint
    url = _build_url(base_url, params) if params else base_url
    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    for attempt in range(MAX_RETRIES):
        try:
            req = requests.Request(
                method=method.upper(),
                url="http://placeholder",
                headers=headers,
                json=json_data,
            )
            prepared = _http_session.prepare_request(req)
            prepared.url = url
            resp = _http_session.send(prepared)
            if resp.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    retry_after = resp.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after else 2 ** attempt
                    print(f"  Rate limited (429). Waiting {wait}s before retry {attempt + 1}/{MAX_RETRIES}...")
                    time.sleep(wait)
                continue
            if not resp.ok:
                print(f"  HTTP {resp.status_code} on {url}")
                print(f"  Error body: {resp.text[:2000]}")
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            print(f"  HTTP error on {url}: {e}")
            raise
    raise Exception(f"Max retries exceeded for {url}")


def _raw_get(url: str, token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    for attempt in range(MAX_RETRIES):
        req = requests.Request("GET", "http://placeholder", headers=headers)
        prepared = _http_session.prepare_request(req)
        prepared.url = url
        resp = _http_session.send(prepared)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"  Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            continue
        if not resp.ok:
            print(f"  HTTP {resp.status_code} on {url}")
            print(f"  Error body: {resp.text[:2000]}")
        resp.raise_for_status()
        return resp.json()
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
    accounts = paginate("adAccounts", token, {"q": "search"})
    print(f"  Found {len(accounts)} active ad accounts")
    return accounts


def fetch_campaigns(token: str, account_id: str) -> list:
    print(f"  Fetching campaigns for account {account_id}...")
    try:
        return paginate(f"adAccounts/{account_id}/adCampaigns", token, {"q": "search"})
    except Exception as e:
        print(f"    Warning: could not fetch campaigns ({e}) — skipping")
        return []


def fetch_creatives_by_campaigns(token: str, account_id: str, campaign_urns: list) -> list:
    if not campaign_urns:
        return []
        
    print(f"  Fetching creatives via criteria search filter for {len(campaign_urns)} campaigns...")
    all_creatives = []
    
    batch_size = 20
    for i in range(0, len(campaign_urns), batch_size):
        batch = campaign_urns[i:i+batch_size]
        campaigns_list_str = f"List({','.join(batch)})"
        
        try:
            creatives = paginate(
                f"adAccounts/{account_id}/creatives",
                token,
                {
                    "q": "criteria",
                    "campaigns": campaigns_list_str
                }
            )
            all_creatives.extend(creatives)
        except Exception as e:
            print(f"    Warning: could not fetch creatives for campaign batch starting index {i} ({e})")
            
    return all_creatives


def fetch_post_details(token: str, post_urn: str) -> dict:
    if not post_urn:
        return {}
    try:
        if "urn:li:share:" in post_urn or "urn:li:ugcPost:" in post_urn:
            post_key = urllib.parse.quote(post_urn, safe="")
        else:
            post_key = extract_id(post_urn)

        url = f"{BASE_URL}posts/{post_key}"
        post_data = _raw_get(url, token)
        
        post_text = post_data.get("commentary", "")
        headline = ""
        landing_page = ""
        
        content = post_data.get("content", {})
        if content:
            article = content.get("article", {})
            if article:
                headline = article.get("title", "")
                landing_page = article.get("source", "")
            else:
                media = content.get("media", {})
                if media:
                    headline = media.get("title", "")
                    
        return {
            "post_text": post_text,
            "headline": headline,
            "landing_page": landing_page
        }
    except Exception as e:
        print(f"    Warning: could not extract details for post URN {post_urn} ({e})")
        return {}


def fetch_creative_level_analytics(token: str, account_id: str) -> list:
    print(f"  Fetching performance analytics by CREATIVE for account {account_id}...")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=1095)

    date_range = (
        f"(start:(year:{start.year},month:{start.month},day:{start.day}),"
        f"end:(year:{end.year},month:{end.month},day:{end.day}))"
    )

    account_urn_encoded = urllib.parse.quote(f"urn:li:sponsoredAccount:{account_id}", safe="")
    fields = "pivotValues,impressions,clicks,actionClicks,totalEngagements"
    
    url = (
        f"{BASE_URL}adAnalytics"
        f"?q=analytics"
        f"&pivot=CREATIVE"
        f"&timeGranularity=DAILY"
        f"&dateRange={date_range}"
        f"&accounts=List({account_urn_encoded})"
        f"&fields={fields}"
    )
    return _raw_get(url, token).get("elements", [])


# --- Main Orchestration ---

def main():
    token = get_valid_token()
    accounts = fetch_ad_accounts(token)

    if not accounts:
        print("No active ad accounts found.")
        return

    consolidated_report = []

    for account in accounts:
        account_id = extract_id(account.get("id", ""))
        print(f"\nProcessing data for Account: {account_id}")
        
        campaigns = fetch_campaigns(token, account_id)
        
        campaign_urns = []
        for c in campaigns:
            raw_id = c.get("id")
            if raw_id:
                urn_str = str(raw_id) if "urn:li:" in str(raw_id) else f"urn:li:sponsoredCampaign:{raw_id}"
                campaign_urns.append(urn_str)
        
        creatives = fetch_creatives_by_campaigns(token, account_id, campaign_urns)
        analytics_records = fetch_creative_level_analytics(token, account_id)

        campaign_map = {}
        for c in campaigns:
            raw_id = c.get("id")
            name = c.get("name", "Unnamed Campaign")
            if raw_id:
                campaign_map[str(raw_id)] = name
                campaign_map[f"urn:li:sponsoredCampaign:{raw_id}"] = name

        metrics_by_creative = {}
        for record in analytics_records:
            pivot_list = record.get("pivotValues", [])
            if not pivot_list:
                continue
                
            pivot_urn = pivot_list[0] if isinstance(pivot_list, list) else pivot_list
            creative_id = extract_id(pivot_urn)
            if not creative_id:
                continue
                
            if creative_id not in metrics_by_creative:
                metrics_by_creative[creative_id] = {
                    "impressions": 0, 
                    "clicks": 0,
                    "action_clicks": 0,
                    "total_engagements": 0
                }
                
            metrics_by_creative[creative_id]["impressions"] += record.get("impressions", 0)
            metrics_by_creative[creative_id]["clicks"] += record.get("clicks", 0)
            metrics_by_creative[creative_id]["total_engagements"] += record.get("totalEngagements", 0)
            
            # FIX: actionClicks is a single flat integer metric under the simple analytics query projection
            metrics_by_creative[creative_id]["action_clicks"] += record.get("actionClicks", 0)

        post_content_cache = {}

        print(f"  Stitching metrics and post texts for {len(creatives)} creative variants...")
        for creative in creatives:
            creative_raw_id = extract_id(creative.get("id"))
            campaign_urn = creative.get("campaign")
            
            campaign_name = campaign_map.get(str(campaign_urn), "Unknown Campaign")

            metrics = metrics_by_creative.get(creative_raw_id, {
                "impressions": 0, "clicks": 0, "action_clicks": 0, "total_engagements": 0
            })
            
            impressions = metrics["impressions"]
            clicks = metrics["clicks"]
            ctr = round((clicks / impressions) * 100, 2) if impressions > 0 else 0.0

            content_src = creative.get("content", {})
            post_urn = content_src.get("reference") or content_src.get("post")
            
            post_text = ""
            headline = ""
            landing_page = ""

            if post_urn:
                if post_urn not in post_content_cache:
                    print(f"    Fetching text details for post variant: {post_urn}")
                    post_content_cache[post_urn] = fetch_post_details(token, post_urn)
                
                details = post_content_cache[post_urn]
                post_text = details.get("post_text", "")
                headline = details.get("headline", "")
                landing_page = details.get("landing_page", "")

            variant_summary = {
                "campaign_name": campaign_name,
                "post_text": post_text,
                "headline": headline,
                "landing_page": landing_page,
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
                "social_action_clicks": metrics["action_clicks"],
                "total_engagements": metrics["total_engagements"]
            }
            consolidated_report.append(variant_summary)

    output_file = Path("consolidated_campaigns.json")
    output_file.write_text(json.dumps(consolidated_report, indent=2), encoding="utf-8")
    print(f"\nSuccess! Variant-level unified profile written to: {output_file.resolve()}")


if __name__ == "__main__":
    main()