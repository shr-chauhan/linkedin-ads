# LinkedIn Ads Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python script that authenticates with LinkedIn OAuth, fetches ad account data (accounts, campaigns, analytics, company engagement), and saves results as JSON files.

**Architecture:** Single-file script (`linkedin_ads.py`) organized into logical sections — token management, API client with retry/pagination, data fetchers, and main orchestration. Tests live in `tests/`.

**Tech Stack:** Python 3.9+, requests, python-dotenv, pytest (tests only)

---

## File Map

| File | Responsibility |
|------|----------------|
| `linkedin_ads/requirements.txt` | Runtime + dev dependencies |
| `linkedin_ads/.env` | Credential template (user fills in) |
| `linkedin_ads/linkedin_ads.py` | All script logic: auth, API client, fetchers, main |
| `linkedin_ads/tests/__init__.py` | Empty — makes tests a package |
| `linkedin_ads/tests/conftest.py` | sys.path setup so tests can import linkedin_ads |
| `linkedin_ads/tests/test_linkedin_ads.py` | Unit tests for pure functions + mocked HTTP |

---

### Task 1: Project scaffold

**Files:**
- Create: `linkedin_ads/requirements.txt`
- Create: `linkedin_ads/.env`
- Create: `linkedin_ads/tests/__init__.py`
- Create: `linkedin_ads/tests/conftest.py`

- [ ] **Step 1: Create requirements.txt**

Create `linkedin_ads/requirements.txt`:
```
requests==2.31.0
python-dotenv==1.0.0
pytest==8.2.0
```

- [ ] **Step 2: Create .env template**

Create `linkedin_ads/.env`:
```
LINKEDIN_CLIENT_ID=your_client_id_here
LINKEDIN_CLIENT_SECRET=your_client_secret_here
LINKEDIN_REDIRECT_URI=https://www.linkedin.com/developers/tools/oauth/redirect
```

- [ ] **Step 3: Create tests/__init__.py**

Create `linkedin_ads/tests/__init__.py` as an empty file.

- [ ] **Step 4: Create tests/conftest.py**

Create `linkedin_ads/tests/conftest.py`:
```python
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
```

- [ ] **Step 5: Install dependencies**

```
cd linkedin_ads
pip install -r requirements.txt
```

Expected: All packages install without error.

- [ ] **Step 6: Verify Python version**

```
python --version
```

Expected: Python 3.9 or later.

---

### Task 2: Token management

**Files:**
- Create: `linkedin_ads/linkedin_ads.py` (initial version)
- Create: `linkedin_ads/tests/test_linkedin_ads.py` (initial version)

- [ ] **Step 1: Write failing tests for token utility functions**

Create `linkedin_ads/tests/test_linkedin_ads.py`:
```python
import json
import time
import pytest
from unittest.mock import patch, MagicMock
import urllib.parse


def test_extract_code_from_url_success():
    from linkedin_ads import extract_code_from_url
    url = "https://www.linkedin.com/developers/tools/oauth/redirect?code=AQT_abc123&state=xyz"
    assert extract_code_from_url(url) == "AQT_abc123"


def test_extract_code_from_url_missing_code():
    from linkedin_ads import extract_code_from_url
    with pytest.raises(ValueError, match="No 'code' parameter"):
        extract_code_from_url("https://example.com/callback?error=access_denied")


def test_is_token_expired_when_expired():
    from linkedin_ads import is_token_expired
    token = {"expires_in": 3600, "obtained_at": int(time.time()) - 4000}
    assert is_token_expired(token) is True


def test_is_token_expired_when_valid():
    from linkedin_ads import is_token_expired
    token = {"expires_in": 3600, "obtained_at": int(time.time())}
    assert is_token_expired(token) is False


def test_extract_id_from_urn():
    from linkedin_ads import extract_id
    assert extract_id("urn:li:sponsoredAccount:123456") == "123456"


def test_extract_id_from_dict():
    from linkedin_ads import extract_id
    assert extract_id({"id": "urn:li:sponsoredCampaign:789"}) == "789"


def test_extract_id_plain_string():
    from linkedin_ads import extract_id
    assert extract_id("42") == "42"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py -v
```

Expected: ImportError or ModuleNotFoundError — `linkedin_ads` doesn't exist yet.

- [ ] **Step 3: Create linkedin_ads.py with token management**

Create `linkedin_ads/linkedin_ads.py`:
```python
import json
import os
import time
import urllib.parse
from datetime import datetime, timedelta
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
TOKEN_FILE = Path("token.json")


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
    return json.loads(TOKEN_FILE.read_text())


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
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```
git add linkedin_ads/linkedin_ads.py linkedin_ads/requirements.txt linkedin_ads/.env linkedin_ads/tests/
git commit -m "feat: scaffold linkedin ads project with token management"
```

---

### Task 3: API client — make_request and paginate

**Files:**
- Modify: `linkedin_ads/linkedin_ads.py` (append API client section)
- Modify: `linkedin_ads/tests/test_linkedin_ads.py` (append API client tests)

- [ ] **Step 1: Write failing tests for make_request and paginate**

Append to `linkedin_ads/tests/test_linkedin_ads.py`:
```python
def test_make_request_success():
    from linkedin_ads import make_request
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"elements": [{"id": "1"}]}
    with patch("linkedin_ads.requests.request", return_value=mock_resp):
        result = make_request("GET", "adAccounts", "fake_token")
    assert result == {"elements": [{"id": "1"}]}


def test_make_request_retries_on_429():
    from linkedin_ads import make_request
    rate_limit_resp = MagicMock()
    rate_limit_resp.status_code = 429

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.json.return_value = {"elements": []}

    with patch("linkedin_ads.requests.request", side_effect=[rate_limit_resp, success_resp]):
        with patch("linkedin_ads.time.sleep") as mock_sleep:
            result = make_request("GET", "adAccounts", "fake_token")
    mock_sleep.assert_called_once_with(1)
    assert result == {"elements": []}


def test_make_request_raises_after_max_retries():
    from linkedin_ads import make_request
    rate_limit_resp = MagicMock()
    rate_limit_resp.status_code = 429

    with patch("linkedin_ads.requests.request", return_value=rate_limit_resp):
        with patch("linkedin_ads.time.sleep"):
            with pytest.raises(Exception, match="Max retries exceeded"):
                make_request("GET", "adAccounts", "fake_token")


def test_paginate_single_page():
    from linkedin_ads import paginate
    response = {"elements": [{"id": "1"}, {"id": "2"}], "paging": {"total": 2}}
    with patch("linkedin_ads.make_request", return_value=response):
        result = paginate("adAccounts", "fake_token")
    assert len(result) == 2


def test_paginate_multiple_pages():
    from linkedin_ads import paginate
    page1 = {"elements": [{"id": str(i)} for i in range(100)], "paging": {"total": 150}}
    page2 = {"elements": [{"id": str(i)} for i in range(100, 150)], "paging": {"total": 150}}
    with patch("linkedin_ads.make_request", side_effect=[page1, page2]):
        result = paginate("adAccounts", "fake_token")
    assert len(result) == 150
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py::test_make_request_success -v
```

Expected: FAIL — `make_request` not defined yet.

- [ ] **Step 3: Append API client to linkedin_ads.py**

Append to `linkedin_ads/linkedin_ads.py` (after the token section):
```python
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
                wait = 2 ** attempt
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
```

- [ ] **Step 4: Run all tests**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py -v
```

Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```
git add linkedin_ads/linkedin_ads.py linkedin_ads/tests/test_linkedin_ads.py
git commit -m "feat: add API client with rate limiting and pagination"
```

---

### Task 4: Data fetchers — ad accounts and campaigns

**Files:**
- Modify: `linkedin_ads/linkedin_ads.py` (append fetcher functions)
- Modify: `linkedin_ads/tests/test_linkedin_ads.py` (append fetcher tests)

- [ ] **Step 1: Write failing tests for ad accounts and campaign fetchers**

Append to `linkedin_ads/tests/test_linkedin_ads.py`:
```python
def test_fetch_ad_accounts():
    from linkedin_ads import fetch_ad_accounts
    mock_accounts = [
        {"id": "urn:li:sponsoredAccount:111", "name": "Test Account", "status": "ACTIVE", "currency": "USD", "type": "ENTERPRISE"}
    ]
    with patch("linkedin_ads.paginate", return_value=mock_accounts):
        result = fetch_ad_accounts("fake_token")
    assert len(result) == 1
    assert result[0]["name"] == "Test Account"


def test_fetch_campaigns():
    from linkedin_ads import fetch_campaigns
    mock_campaigns = [
        {"id": "urn:li:sponsoredCampaign:999", "name": "Campaign A", "status": "ACTIVE"}
    ]
    with patch("linkedin_ads.paginate", return_value=mock_campaigns):
        result = fetch_campaigns("fake_token", "111")
    assert len(result) == 1
    assert result[0]["name"] == "Campaign A"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py::test_fetch_ad_accounts -v
```

Expected: FAIL — `fetch_ad_accounts` not defined yet.

- [ ] **Step 3: Append fetcher functions to linkedin_ads.py**

Append to `linkedin_ads/linkedin_ads.py`:
```python
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
```

- [ ] **Step 4: Run all tests**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py -v
```

Expected: All 14 tests PASS.

- [ ] **Step 5: Commit**

```
git add linkedin_ads/linkedin_ads.py linkedin_ads/tests/test_linkedin_ads.py
git commit -m "feat: add ad accounts and campaign fetchers"
```

---

### Task 5: Analytics fetchers

**Files:**
- Modify: `linkedin_ads/linkedin_ads.py` (append analytics functions)
- Modify: `linkedin_ads/tests/test_linkedin_ads.py` (append analytics tests)

- [ ] **Step 1: Write failing tests for analytics fetchers**

Append to `linkedin_ads/tests/test_linkedin_ads.py`:
```python
def test_fetch_campaign_analytics_batches_by_10():
    from linkedin_ads import fetch_campaign_analytics
    campaign_ids = [str(i) for i in range(25)]
    mock_resp = {"elements": [{"impressions": 100}]}
    with patch("linkedin_ads.make_request", return_value=mock_resp) as mock_req:
        result = fetch_campaign_analytics("fake_token", campaign_ids)
    # 25 campaigns → 3 batches: 10 + 10 + 5
    assert mock_req.call_count == 3
    assert len(result) == 3  # one element per batch response


def test_fetch_campaign_analytics_includes_required_params():
    from linkedin_ads import fetch_campaign_analytics
    mock_resp = {"elements": []}
    with patch("linkedin_ads.make_request", return_value=mock_resp) as mock_req:
        fetch_campaign_analytics("fake_token", ["123"])
    call_params = mock_req.call_args[1]["params"]
    assert call_params["pivots"] == "List(CAMPAIGN)"
    assert call_params["timeGranularity"] == "DAILY"
    assert call_params["q"] == "statistics"


def test_fetch_company_engagement_uses_company_pivot():
    from linkedin_ads import fetch_company_engagement
    mock_resp = {"elements": [{"impressions": 50}]}
    with patch("linkedin_ads.make_request", return_value=mock_resp) as mock_req:
        result = fetch_company_engagement("fake_token", ["456"])
    call_params = mock_req.call_args[1]["params"]
    assert call_params["pivots"] == "List(COMPANY)"
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py::test_fetch_campaign_analytics_batches_by_10 -v
```

Expected: FAIL — `fetch_campaign_analytics` not defined yet.

- [ ] **Step 3: Append analytics functions to linkedin_ads.py**

Append to `linkedin_ads/linkedin_ads.py`:
```python
# --- Analytics fetchers ---

CAMPAIGN_ANALYTICS_FIELDS = (
    "impressions,clicks,costInLocalCurrency,externalWebsiteConversions,"
    "costPerClick,clickThroughRate,costPerConversion,pivotValues,dateRange"
)

COMPANY_ENGAGEMENT_FIELDS = "impressions,clicks,costInLocalCurrency,pivotValues"


def _build_date_range_param() -> str:
    end = datetime.utcnow()
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
```

- [ ] **Step 4: Run all tests**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py -v
```

Expected: All 17 tests PASS.

- [ ] **Step 5: Commit**

```
git add linkedin_ads/linkedin_ads.py linkedin_ads/tests/test_linkedin_ads.py
git commit -m "feat: add campaign analytics and company engagement fetchers"
```

---

### Task 6: Main orchestration

**Files:**
- Modify: `linkedin_ads/linkedin_ads.py` (append main function)
- Modify: `linkedin_ads/tests/test_linkedin_ads.py` (append orchestration test)

- [ ] **Step 1: Write failing test for main orchestration**

Append to `linkedin_ads/tests/test_linkedin_ads.py`:
```python
def test_main_saves_all_json_files(tmp_path, monkeypatch):
    from linkedin_ads import main
    monkeypatch.chdir(tmp_path)

    mock_accounts = [{"id": "urn:li:sponsoredAccount:111", "name": "Acct", "status": "ACTIVE", "currency": "USD", "type": "ENTERPRISE"}]
    mock_campaigns = [{"id": "urn:li:sponsoredCampaign:999", "name": "Camp", "status": "ACTIVE"}]
    mock_analytics = [{"impressions": 100}]
    mock_engagement = [{"impressions": 50}]

    with patch("linkedin_ads.get_valid_token", return_value="fake_token"), \
         patch("linkedin_ads.fetch_ad_accounts", return_value=mock_accounts), \
         patch("linkedin_ads.fetch_campaign_groups", return_value=[]), \
         patch("linkedin_ads.fetch_campaigns", return_value=mock_campaigns), \
         patch("linkedin_ads.fetch_campaign_analytics", return_value=mock_analytics), \
         patch("linkedin_ads.fetch_company_engagement", return_value=mock_engagement):
        main()

    assert (tmp_path / "ad_accounts.json").exists()
    assert (tmp_path / "campaigns.json").exists()
    assert (tmp_path / "analytics.json").exists()
    assert (tmp_path / "company_engagement.json").exists()

    accounts_data = json.loads((tmp_path / "ad_accounts.json").read_text())
    assert len(accounts_data) == 1
    assert accounts_data[0]["name"] == "Acct"
```

- [ ] **Step 2: Run test to confirm it fails**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py::test_main_saves_all_json_files -v
```

Expected: FAIL — `main` not defined yet.

- [ ] **Step 3: Append main function to linkedin_ads.py**

Append to `linkedin_ads/linkedin_ads.py`:
```python
# --- Main orchestration ---

def main():
    token = get_valid_token()

    # 1. Ad accounts
    accounts = fetch_ad_accounts(token)
    Path("ad_accounts.json").write_text(json.dumps(accounts, indent=2))
    print(f"Saved ad_accounts.json ({len(accounts)} accounts)\n")

    # 2. Campaigns (groups + campaigns per account)
    all_campaign_ids = []
    all_campaigns_data = []
    for account in accounts:
        account_id = extract_id(account.get("id", ""))
        groups = fetch_campaign_groups(token, account_id)
        campaigns = fetch_campaigns(token, account_id)
        for c in campaigns:
            cid = extract_id(c.get("id", ""))
            if cid:
                all_campaign_ids.append(cid)
        all_campaigns_data.append({
            "account_id": account_id,
            "campaign_groups": groups,
            "campaigns": campaigns,
        })
    Path("campaigns.json").write_text(json.dumps(all_campaigns_data, indent=2))
    print(f"Saved campaigns.json ({len(all_campaign_ids)} campaigns total)\n")

    # 3. Campaign analytics (last 30 days, CAMPAIGN pivot, DAILY granularity)
    if all_campaign_ids:
        analytics = fetch_campaign_analytics(token, all_campaign_ids)
        Path("analytics.json").write_text(json.dumps(analytics, indent=2))
        print(f"Saved analytics.json ({len(analytics)} records)\n")
    else:
        print("No campaigns found — skipping analytics\n")

    # 4. Company engagement (COMPANY pivot)
    if all_campaign_ids:
        engagement = fetch_company_engagement(token, all_campaign_ids)
        Path("company_engagement.json").write_text(json.dumps(engagement, indent=2))
        print(f"Saved company_engagement.json ({len(engagement)} records)\n")
    else:
        print("No campaigns found — skipping company engagement\n")

    print("Done!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests**

```
cd linkedin_ads
pytest tests/test_linkedin_ads.py -v
```

Expected: All 18 tests PASS.

- [ ] **Step 5: Final commit**

```
git add linkedin_ads/linkedin_ads.py linkedin_ads/tests/test_linkedin_ads.py
git commit -m "feat: add main orchestration — complete linkedin ads integration"
```

---

## Self-Review

**Spec coverage check:**
- [x] Credentials read from .env via python-dotenv — Task 1, 2
- [x] OAuth manual copy-paste flow (print URL, input redirect URL, extract code) — Task 2 (`_run_full_auth_flow`)
- [x] Token stored in token.json — Task 2 (`save_token` / `load_token`)
- [x] Skip auth on subsequent runs if token valid — Task 2 (`get_valid_token`)
- [x] Refresh token when access token expired — Task 2 (`get_valid_token`)
- [x] Re-run full auth when refresh token expired — Task 2 (`get_valid_token` fallback)
- [x] Scopes: r_ads r_ads_reporting rw_ads r_organization_admin r_organization_social — Task 2 (`SCOPES`)
- [x] ad_accounts.json — Task 4 + 6
- [x] campaigns.json (groups + campaigns per account) — Task 4 + 6
- [x] analytics.json (last 30 days, CAMPAIGN pivot, DAILY) — Task 5 + 6
- [x] company_engagement.json (COMPANY pivot) — Task 5 + 6
- [x] Required headers on every request — Task 3 (`make_request`)
- [x] Pagination via start + count (max 100 per page) — Task 3 (`paginate`)
- [x] 429 exponential backoff, max 3 retries — Task 3 (`make_request`)
- [x] Clear print logs for each step — all fetcher functions
- [x] try/except with meaningful error messages — Task 3 (`make_request`)
- [x] LinkedIn-Version: 202604 — Task 3 (`API_VERSION`)
- [x] Base URL https://api.linkedin.com/rest/ — Task 2 (`BASE_URL`)
- [x] Batch campaign analytics in groups of 10 — Task 5
- [x] dateRange nested object format — Task 5 (`_build_date_range_param`)
- [x] requests only (no SDK) + python-dotenv — Task 1

**Note on "spend" field:** The spec lists `spend` as a metric name but the LinkedIn API field is `costInLocalCurrency`. The plan uses the correct API field name.

**Placeholder scan:** No TBDs, TODOs, or vague instructions present.

**Type consistency:** `token: str`, `account_id: str`, `campaign_ids: list` used consistently across Tasks 2–6. `extract_id` used uniformly in Task 6 main function.
