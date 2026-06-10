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


def test_fetch_campaign_groups():
    from linkedin_ads import fetch_campaign_groups
    mock_groups = [
        {"id": "urn:li:sponsoredCampaignGroup:555", "name": "Group A", "status": "ACTIVE"}
    ]
    with patch("linkedin_ads.paginate", return_value=mock_groups) as mock_pag:
        result = fetch_campaign_groups("fake_token", "111")
    assert len(result) == 1
    assert result[0]["name"] == "Group A"
    mock_pag.assert_called_once_with(
        "adCampaignGroups", "fake_token",
        {"q": "search", "search.account": "urn:li:sponsoredAccount:111"}
    )


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
