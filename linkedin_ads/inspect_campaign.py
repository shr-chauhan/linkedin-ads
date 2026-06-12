import json
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

# --- Settings & Setup ---
BASE_URL = "https://api.linkedin.com/rest/"
API_VERSION = "202604"
TOKEN_FILE = Path(__file__).parent / "token.json"
TARGET_CAMPAIGN_ID = "455229433"

def load_token_string() -> str:
    if not TOKEN_FILE.exists():
        print(f"Error: Could not find {TOKEN_FILE.name}. Run your main script first to authenticate.")
        sys.exit(1)
    try:
        data = json.loads(TOKEN_FILE.read_text())
        return data["access_token"]
    except Exception as e:
        print(f"Error reading token configuration: {e}")
        sys.exit(1)

def extract_id(value) -> str:
    if isinstance(value, dict):
        value = value.get("id", "")
    value = str(value)
    return value.split(":")[-1] if ":" in value else value

def get_linkedin_raw(url: str, token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        print(f"  API Request Warning: Status {resp.status_code} returned on URL:\n  {url}")
        try:
            return {"_api_error_payload": resp.json()}
        except:
            return {"_api_error_text": resp.text[:1000]}
    return resp.json()


def fetch_targeting_translations(urn_list, token):
    if not urn_list:
        return {}

    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }

    translations = {}
    urns = sorted(set(u for u in urn_list if not u.startswith("urn:li:adTargetingFacet:")))
    batch_size = 20

    print(f"├── Resolving {len(urns)} targeting entities...")

    for i in range(0, len(urns), batch_size):
        batch = urns[i:i + batch_size]
        encoded_urns = [urllib.parse.quote(urn, safe="") for urn in batch]
        urn_param = f"List({','.join(encoded_urns)})"

        lookup_url = (
            f"{BASE_URL}adTargetingEntities"
            f"?q=urns"
            f"&queryVersion=QUERY_USES_URNS"
            f"&urns={urn_param}"
        )

        resp = requests.get(lookup_url, headers=headers)
        if not resp.ok:
            print(f"Failed batch {i}-{i+len(batch)} status={resp.status_code}")
            continue

        payload = resp.json()
        for element in payload.get("elements", []):
            urn = element.get("urn")
            name = element.get("name")
            if urn and name:
                translations[urn] = name

    print(f"├── Successfully resolved {len(translations)} entities")
    return translations


def augment_targeting_criteria(item, translations: dict):
    if isinstance(item, list):
        new_list = []
        for element in item:
            if isinstance(element, str):
                if element in translations:
                    new_list.append({"urn": element, "resolved_name": translations[element]})
                elif "urn:li:organization:" in element:
                    new_list.append({"urn": element, "resolved_name": "Aisepedia (Excluded Corporate Page Node)"})
                else:
                    new_list.append(element)
            else:
                new_list.append(augment_targeting_criteria(element, translations))
        return new_list

    if isinstance(item, dict):
        new_dict = {}
        for key, value in item.items():
            if isinstance(key, str) and ("urn:li:adTargetingFacet:" in key or "urn:li:skill:" in key) and isinstance(value, list):
                processed_list = []
                for entry in value:
                    if isinstance(entry, str) and entry in translations:
                        processed_list.append({"urn": entry, "resolved_name": translations[entry]})
                    elif isinstance(entry, str) and "urn:li:organization:" in entry:
                        processed_list.append({"urn": entry, "resolved_name": "Aisepedia (Excluded Corporate Page Node)"})
                    else:
                        processed_list.append(entry)
                new_dict[key] = processed_list
            else:
                new_dict[key] = augment_targeting_criteria(value, translations)
        return new_dict

    return item

def extract_all_urns_from_targeting(criteria_dict: dict) -> list:
    urns = []
    if isinstance(criteria_dict, dict):
        for key, val in criteria_dict.items():
            if "urn:li:" in key:
                urns.append(key)
            urns.extend(extract_all_urns_from_targeting(val))
    elif isinstance(criteria_dict, list):
        for item in criteria_dict:
            urns.extend(extract_all_urns_from_targeting(item))
    elif isinstance(criteria_dict, str) and "urn:li:" in criteria_dict:
        urns.append(criteria_dict)
    return urns


def main():
    token = load_token_string()
    print(f"🚀 Initializing deep raw metadata inspection for Campaign: {TARGET_CAMPAIGN_ID}...")
    
    account_id = "514146109" 
    campaign_urn_string = f"urn:li:sponsoredCampaign:{TARGET_CAMPAIGN_ID}"
    
    campaign_urn_encoded = urllib.parse.quote(campaign_urn_string, safe="")
    account_urn_encoded = urllib.parse.quote(f"urn:li:sponsoredAccount:{account_id}", safe="")

    # --- 1. Fetch Core Campaign Data ---
    print(f"├── Querying direct entity mapping path at /adAccounts/{account_id}/adCampaigns/{TARGET_CAMPAIGN_ID}...")
    direct_camp_url = f"{BASE_URL}adAccounts/{account_id}/adCampaigns/{TARGET_CAMPAIGN_ID}"
    campaign_direct_data = get_linkedin_raw(direct_camp_url, token)

    # --- 2. Handle Targeting Transformations ---
    targeting_root = campaign_direct_data.get("targetingCriteria", {})
    all_extracted_urns = extract_all_urns_from_targeting(targeting_root)
    
    if all_extracted_urns:
        dictionary_mappings = fetch_targeting_translations(all_extracted_urns, token)
        augmented_targeting = augment_targeting_criteria(targeting_root, dictionary_mappings)
    else:
        augmented_targeting = targeting_root

    # --- 3. Resolve Associated Entity Name (Organization) ---
    associated_entity_urn = campaign_direct_data.get("associatedEntity")
    associated_entity_payload = None

    if associated_entity_urn:
        print(f"├── Resolving Campaign Associated Entity: {associated_entity_urn}...")
        entity_resolved = fetch_targeting_translations([associated_entity_urn], token)
        resolved_name = entity_resolved.get(associated_entity_urn)

        if not resolved_name and "urn:li:organization:" in associated_entity_urn:
            resolved_name = "Aisepedia"

        associated_entity_payload = {
            "urn": associated_entity_urn,
            "resolved_name": resolved_name or "Unknown Entity Reference"
        }

    # --- 4. Format Scheduling & Cost Data ---
    run_schedule = campaign_direct_data.get("runSchedule", {})
    start_ms = run_schedule.get("start")
    end_ms = run_schedule.get("end")
    
    start_date = datetime.fromtimestamp(start_ms / 1000.0, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') if start_ms else None
    end_date = datetime.fromtimestamp(end_ms / 1000.0, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') if end_ms else None

    daily_budget_raw = campaign_direct_data.get("dailyBudget", {})
    unit_cost_raw = campaign_direct_data.get("unitCost", {})

    output_payload = {
        "campaign": {
            "campaign_id": TARGET_CAMPAIGN_ID,
            "campaign_name": campaign_direct_data.get("name"),
            "status": campaign_direct_data.get("status"),
            "objective_type": campaign_direct_data.get("objectiveType"),
            "optimization_target_type": campaign_direct_data.get("optimizationTargetType"),
            "cost_type": campaign_direct_data.get("costType"),
            "associated_entity": associated_entity_payload,
            "start_date": start_date,
            "end_date": end_date,
            "daily_budget": {
                "amount": float(daily_budget_raw.get("amount", 0)) if daily_budget_raw.get("amount") else 0.0,
                "currency": daily_budget_raw.get("currencyCode")
            },
            "unit_cost": {
                "amount": float(unit_cost_raw.get("amount", 0)) if unit_cost_raw.get("amount") else 0.0,
                "currency": unit_cost_raw.get("currencyCode")
            },
            "targeting": augmented_targeting,
            "creatives": []
        }
    }

    # --- 5. Fetch Child Creatives ---
    print("├── Crawling for all associated child creatives...")
    creatives_url = (
        f"{BASE_URL}adAccounts/{account_id}/creatives"
        f"?q=criteria"
        f"&campaigns=List({campaign_urn_encoded})"
    )
    creatives_data = get_linkedin_raw(creatives_url, token)
    creative_elements = creatives_data.get("elements", []) if isinstance(creatives_data, dict) else []

    # --- 6. Fetch Global Analytics Metrics ---
    print("├── Dumping statistical engine analytics rows...")
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=1095)
    date_range_str = f"(start:(year:{start_dt.year},month:{start_dt.month},day:{start_dt.day}),end:(year:{end_dt.year},month:{end_dt.month},day:{end_dt.day}))"
    
    all_metrics = "pivotValues,impressions,clicks,actionClicks,totalEngagements,costInLocalCurrency"
    stats_url = (
        f"{BASE_URL}adAnalytics?q=analytics&pivot=CREATIVE&timeGranularity=ALL"
        f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={all_metrics}"
    )
    all_analytics = get_linkedin_raw(stats_url, token)
    analytics_elements = all_analytics.get("elements", []) if isinstance(all_analytics, dict) else []

    performance_map = {}
    for row in analytics_elements:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            c_id = extract_id(p_vals[0])
            performance_map[c_id] = row

    # --- 7. Assemble Hierarchical Creative Blocks ---
    for creative in creative_elements:
        creative_urn = creative.get("id", "")
        creative_id = extract_id(creative_urn)
        print(f"│   ├── Processing Child Tree Context for Creative: {creative_id}...")

        content_block = creative.get("content", {})
        post_urn = content_block.get("reference") or content_block.get("post")
        post_data = {}

        if post_urn:
            post_key = urllib.parse.quote(post_urn, safe="") if any(x in post_urn for x in ["share:", "ugcPost:"]) else extract_id(post_urn)
            post_endpoint_url = f"{BASE_URL}posts/{post_key}"
            raw_post = get_linkedin_raw(post_endpoint_url, token)
            
            # Extract Image URN References
            image_urn = None
            image_url = None
            content_details = raw_post.get("content", {})
            
            if "article" in content_details:
                image_urn = content_details["article"].get("thumbnail")
            elif "mediaComponent" in content_details:
                image_urn = content_details["mediaComponent"].get("thumbnail")

            # Correctly escape single resource entity lookups
            if image_urn:
                print(f"│   │   ├── Resolving image asset layout properties for: {image_urn}...")
                encoded_image_urn = urllib.parse.quote(image_urn, safe="")
                image_lookup_url = f"{BASE_URL}images/{encoded_image_urn}"
                raw_image_data = get_linkedin_raw(image_lookup_url, token)
                image_url = raw_image_data.get("downloadUrl")

            post_data = {
                "post_id": raw_post.get("id"),
                "title": content_details.get("article", {}).get("title"),
                "commentary": raw_post.get("commentary"),
                "landing_page": raw_post.get("contentLandingPage"),
                "cta": raw_post.get("contentCallToActionLabel"),
                "asset_image": {
                    "urn": image_urn,
                    "download_url": image_url
                }
            }

        perf_row = performance_map.get(creative_id, {})
        impressions = perf_row.get("impressions", 0)
        clicks = perf_row.get("clicks", 0)
        ctr = round((clicks / impressions) * 100, 2) if impressions else 0
        
        raw_spend = perf_row.get("costInLocalCurrency", 0)
        spend = round(float(raw_spend), 2) if raw_spend else 0.0

        performance_data = {
            "impressions": impressions,
            "clicks": clicks,
            "ctr_percent": ctr,
            "engagements": perf_row.get("totalEngagements", 0),
            "action_clicks": perf_row.get("actionClicks", 0),
            "spend": spend
        }

        output_payload["campaign"]["creatives"].append({
            "creative_id": creative_id,
            "creative_name": creative.get("name"),
            "post": post_data,
            "performance": performance_data
        })

    # --- Write Clean Output To Disk ---
    out_file = Path("raw_campaign_455229433_debug.json")
    out_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    print(f"\n✨ Inspection Completed! Structured JSON written to:\n{out_file.resolve()}\n")

if __name__ == "__main__":
    main()