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
