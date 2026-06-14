from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from campaign_report import TokenExpiredError, build_campaign_report

# Drop emoji/box-drawing characters the console can't display (e.g. default
# Windows cp1252) instead of crashing.
sys.stdout.reconfigure(errors="ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CAMPAIGNS_FILE = Path(os.environ.get("CAMPAIGNS_FILE", PROJECT_ROOT / "campaigns.json"))
CACHE_DIR = Path(os.environ.get("CACHE_DIR", PROJECT_ROOT / "cache"))
TOKEN_FILE = Path(os.environ.get("TOKEN_FILE", PROJECT_ROOT / "linkedin_ads" / "token.json"))
CACHE_TTL_SECONDS = 3600

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_campaigns_config() -> list[dict]:
    if not CAMPAIGNS_FILE.exists():
        return []
    return json.loads(CAMPAIGNS_FILE.read_text(encoding="utf-8"))


def read_token() -> str | None:
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        return data.get("access_token")
    except (json.JSONDecodeError, OSError):
        return None


@app.get("/campaigns")
def list_campaigns():
    return load_campaigns_config()


@app.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, refresh: bool = Query(False)):
    config = next((c for c in load_campaigns_config() if c["id"] == campaign_id), None)
    if config is None:
        raise HTTPException(status_code=404, detail="Unknown campaign id")

    cache_file = CACHE_DIR / f"report_{campaign_id}.json"
    if not refresh and cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        if age_seconds < CACHE_TTL_SECONDS:
            return cached

    token = read_token()
    if not token:
        raise HTTPException(status_code=401, detail={"error": "token_expired"})

    try:
        report = build_campaign_report(config["account_id"], campaign_id, token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail={"error": "token_expired"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "fetch_failed", "message": str(e)})

    result = {
        "campaign": report["campaign"],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    CACHE_DIR.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result
