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
