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

    # Remove facet URNs. Only resolve actual entities.
    urns = sorted(
        set(
            u
            for u in urn_list
            if not u.startswith("urn:li:adTargetingFacet:")
        )
    )

    batch_size = 20

    print(f"├── Resolving {len(urns)} targeting entities...")

    for i in range(0, len(urns), batch_size):

        batch = urns[i:i + batch_size]

        encoded_urns = [
            urllib.parse.quote(urn, safe="")
            for urn in batch
        ]

        urn_param = f"List({','.join(encoded_urns)})"

        lookup_url = (
            f"{BASE_URL}adTargetingEntities"
            f"?q=urns"
            f"&queryVersion=QUERY_USES_URNS"
            f"&urns={urn_param}"
        )

        resp = requests.get(
            lookup_url,
            headers=headers
        )

        if not resp.ok:
            print(
                f"Failed batch {i}-{i+len(batch)} "
                f"status={resp.status_code}"
            )
            print(resp.text)
            continue

        payload = resp.json()

        for element in payload.get("elements", []):

            urn = element.get("urn")
            name = element.get("name")

            if urn and name:
                translations[urn] = name

    print(
        f"├── Successfully resolved "
        f"{len(translations)} entities"
    )

    return translations


def _fetch_targeting_translations(urn_list: list, token: str) -> dict:
    """
    Groups targeting URN strings, maps them to valid API targeting entity types,
    and fetches translations dynamically from LinkedIn in chunks of 10.
    """
    if not urn_list:
        return {}
    
    translations = {}
    
    facet_to_entity_type = {
        "skills": "skill",
        "industries": "industry",
        "functions": "function",
        "interfaceLocales": "locale",
        "locations": "geo",
        "degrees": "degree",
        "fieldsOfStudy": "fieldOfStudy"
    }
    
    grouped_urns = {}
    for urn in set(urn_list):
        parts = urn.split(":")
        if len(parts) >= 3:
            raw_tag = parts[2]
            if raw_tag == "adTargetingFacet" and len(parts) >= 4:
                urn_type = facet_to_entity_type.get(parts[3], parts[3])
            else:
                urn_type = facet_to_entity_type.get(raw_tag, raw_tag)
                
            grouped_urns.setdefault(urn_type, []).append(urn)

    print(f"├── Translating targeting fields across {len(grouped_urns)} distinct metadata categories...")

    for urn_type, type_urns in grouped_urns.items():
        if urn_type in ["organization", "employer", "adTargetingFacet"]:
            continue
            
        batch_size = 10
        for i in range(0, len(type_urns), batch_size):
            batch = type_urns[i:i+batch_size]
            
            cleaned_batch = []
            for item in batch:
                if "urn:li:adTargetingFacet:" in item:
                    item = f"urn:li:{urn_type}:{item.split(':')[-1]}"
                # Percent encode internal list values individually
                cleaned_batch.append(urllib.parse.quote(item, safe=""))
                    
            urn_param = f"List({','.join(cleaned_batch)})"
            
            # Keep structural parentheses/lists clean, encode elements
            lookup_url = (
                f"{BASE_URL}adTargetingEntities?q=urns&queryVersion=QUERY_USES_URNS"
                f"&type={urn_type}&urns={urn_param}"
            )
            
            headers = {
                "Authorization": f"Bearer {token}",
                "LinkedIn-Version": API_VERSION,
                "X-Restli-Protocol-Version": "2.0.0",
            }
            resp = requests.get(lookup_url, headers=headers)
            
            if resp.ok:
                try:
                    elements = resp.json().get("elements", [])
                    for element in elements:
                        remote_urn = element.get("urn")
                        name = element.get("name")
                        if remote_urn and name:
                            translations[remote_urn] = name
                            short_id = remote_urn.split(":")[-1]
                            for original_urn in batch:
                                if original_urn.endswith(f":{short_id}"):
                                    translations[original_urn] = name
                except Exception as e:
                    print(f"  ⚠️ Error parsing element responses for type {urn_type}: {e}")
            else:
                if urn_type == "geo":
                    for g_urn in batch:
                        translations[g_urn] = "United States (Geographic Region)"
                elif urn_type == "locale":
                    for l_urn in batch:
                        translations[l_urn] = "English (US)"

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
    
    inspection_payload = {
        "target_campaign_id": TARGET_CAMPAIGN_ID,
        "inspection_timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": {}
    }

    account_id = "514146109" 
    campaign_urn_string = f"urn:li:sponsoredCampaign:{TARGET_CAMPAIGN_ID}"
    
    # Pre-encode target values safely matching your working snippet
    campaign_urn_encoded = urllib.parse.quote(campaign_urn_string, safe="")
    account_urn_encoded = urllib.parse.quote(f"urn:li:sponsoredAccount:{account_id}", safe="")

    # --- 1. Campaign Search Endpoint ---
    print("├── Querying /adCampaigns looking for specific campaign metadata rows...")
    search_url = (
        f"{BASE_URL}adAccounts/{account_id}/adCampaigns"
        f"?q=search"
        f"&search=(id:(values:List({campaign_urn_encoded})))"
    )
    inspection_payload["endpoints"]["adCampaigns_search_payload"] = get_linkedin_raw(search_url, token)

    # --- 2. Direct Campaign Entity Path ---
    print(f"├── Querying direct entity mapping path at /adAccounts/{account_id}/adCampaigns/{TARGET_CAMPAIGN_ID}...")
    direct_camp_url = f"{BASE_URL}adAccounts/{account_id}/adCampaigns/{TARGET_CAMPAIGN_ID}"
    campaign_direct_data = get_linkedin_raw(direct_camp_url, token)
    inspection_payload["endpoints"]["adCampaigns_direct_entity"] = campaign_direct_data

    # --- 3. Child Creatives ---
    print("├── Crawling for all associated child creatives...")
    creatives_url = (
        f"{BASE_URL}adAccounts/{account_id}/creatives"
        f"?q=criteria"
        f"&campaigns=List({campaign_urn_encoded})"
    )
    creatives_data = get_linkedin_raw(creatives_url, token)
    inspection_payload["endpoints"]["creatives_criteria_payload"] = creatives_data

    # --- 4. Deep Inspection of Backing Social Posts ---
    print("├── Inspecting underlying organic post objects and commentary blocks...")
    inspection_payload["endpoints"]["resolved_posts"] = []
    
    creative_elements = creatives_data.get("elements", []) if isinstance(creatives_data, dict) else []
    for creative in creative_elements:
        c_id = extract_id(creative.get("id", ""))
        content_block = creative.get("content", {})
        post_urn = content_block.get("reference") or content_block.get("post")
        
        if post_urn:
            post_key = urllib.parse.quote(post_urn, safe="") if any(x in post_urn for x in ["share:", "ugcPost:"]) else extract_id(post_urn)
            post_endpoint_url = f"{BASE_URL}posts/{post_key}"
            print(f"│   ├── Fetching /posts/{post_key} for Creative URN variant: {c_id}...")
            post_payload = get_linkedin_raw(post_endpoint_url, token)
            inspection_payload["endpoints"]["resolved_posts"].append({
                "source_creative_id": c_id,
                "source_post_urn": post_urn,
                "raw_post_payload": post_payload
            })

    # --- 5. Analytics Endpoint ---
    print("├── Dumping statistical engine analytics rows...")

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=1095)

    date_range_str = (
        f"(start:(year:{start_dt.year},month:{start_dt.month},day:{start_dt.day}),"
        f"end:(year:{end_dt.year},month:{end_dt.month},day:{end_dt.day}))"
    )

    all_metrics = (
        "pivotValues,"
        "impressions,"
        "clicks,"
        "actionClicks,"
        "totalEngagements,"
        "costInLocalCurrency"
    )

    stats_url = (
        f"{BASE_URL}adAnalytics"
        f"?q=analytics"
        f"&pivot=CREATIVE"
        f"&timeGranularity=ALL"
        f"&dateRange={date_range_str}"
        f"&accounts=List({account_urn_encoded})"
        f"&fields={all_metrics}"
    )

    all_analytics = get_linkedin_raw(stats_url, token)

    # Debug: save raw analytics response
    inspection_payload["endpoints"]["adAnalytics_raw"] = all_analytics

    target_creative_ids = {
        extract_id(c.get("id", ""))
        for c in creative_elements
    }

    print("\nTarget Creative IDs:")
    print(target_creative_ids)

    creative_performance = []

    if isinstance(all_analytics, dict):

        print(
            f"Analytics rows returned: "
            f"{len(all_analytics.get('elements', []))}"
        )

        for row in all_analytics.get("elements", []):

            p_vals = row.get("pivotValues", [])

            if not p_vals:
                continue

            pivot = p_vals[0]
            row_creative_id = extract_id(pivot)

            print(
                f"Analytics Pivot: {pivot} "
                f"-> {row_creative_id}"
            )

            if row_creative_id in target_creative_ids:

                print("MATCHED")

                creative_performance.append({
                    "creative_id": row_creative_id,
                    "impressions": row.get("impressions", 0),
                    "clicks": row.get("clicks", 0),
                    "action_clicks": row.get("actionClicks", 0),
                    "engagements": row.get("totalEngagements", 0),
                    "spend": row.get("costInLocalCurrency", 0)
                })

    inspection_payload["endpoints"]["creative_performance"] = creative_performance

    print(
        f"│   └── Matched "
        f"{len(creative_performance)} creative analytics rows."
    )
    # print("├── Dumping statistical engine analytics rows...")
    # end_dt = datetime.now(timezone.utc)
    # start_dt = end_dt - timedelta(days=90)
    
    # date_range_str = (
    #     f"(start:(year:{start_dt.year},month:{start_dt.month},day:{start_dt.day}),"
    #     f"end:(year:{end_dt.year},month:{end_dt.month},day:{end_dt.day}))"
    # )
    
    # # all_metrics = (
    # #     "pivotValues,impressions,clicks,totalEngagements,costInLocalCurrency,externalClicks,"
    # #     "likes,comments,shares,actionClicks"
    # # )
    
    # all_metrics = (
    # "pivotValues,impressions,clicks,totalEngagements,"
    # "costInLocalCurrency,"
    # "likes,comments,shares,"
    # "actionClicks"
    # )
    
    # stats_url = (
    #     f"{BASE_URL}adAnalytics"
    #     f"?q=analytics"
    #     f"&pivot=CREATIVE"
    #     f"&timeGranularity=DAILY"
    #     f"&dateRange={date_range_str}"
    #     f"&accounts=List({account_urn_encoded})"
    #     f"&fields={all_metrics}"
    # )
    
    # all_analytics = get_linkedin_raw(stats_url, token)
    
    # target_creative_ids = {extract_id(c.get("id", "")) for c in creative_elements}
    # filtered_rows = []
    
    # if isinstance(all_analytics, dict) and "elements" in all_analytics:
    #     for row in all_analytics.get("elements", []):
    #         p_vals = row.get("pivotValues", [])
    #         if p_vals:
    #             row_creative_id = extract_id(p_vals[0])
    #             if row_creative_id in target_creative_ids:
    #                 filtered_rows.append(row)
                
    # inspection_payload["endpoints"]["adAnalytics_filtered_time_series_rows"] = filtered_rows
    # print(f"│   └── Isolated {len(filtered_rows)} daily performance log records.")

    # --- 6. TARGETING TRANSLATION ENGINE ---
    targeting_root = campaign_direct_data.get("targetingCriteria", {})
    all_extracted_urns = extract_all_urns_from_targeting(targeting_root)
    
    if all_extracted_urns:
        dictionary_mappings = fetch_targeting_translations(all_extracted_urns, token)
        augmented_targeting = augment_targeting_criteria(targeting_root, dictionary_mappings)
        
        if "adCampaigns_direct_entity" in inspection_payload["endpoints"] and isinstance(inspection_payload["endpoints"]["adCampaigns_direct_entity"], dict):
            inspection_payload["endpoints"]["adCampaigns_direct_entity"]["targetingCriteria"] = augmented_targeting
        
        search_elements = inspection_payload["endpoints"]["adCampaigns_search_payload"].get("elements", []) if isinstance(inspection_payload["endpoints"]["adCampaigns_search_payload"], dict) else []
        for element in search_elements:
            if isinstance(element, dict) and "targetingCriteria" in element:
                element["targetingCriteria"] = augment_targeting_criteria(element["targetingCriteria"], dictionary_mappings)

    # --- Write Results to Disk ---
    out_file = Path("raw_campaign_455229433_debug.json")
    out_file.write_text(json.dumps(inspection_payload, indent=2), encoding="utf-8")
    print(f"\n✨ Inspection Completed! Clean text-translated JSON written to:\n{out_file.resolve()}\n")

if __name__ == "__main__":
    main()