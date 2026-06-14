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
TARGET_CAMPAIGN_ID = "593700663"
TOP_COMPANIES_LIMIT = 20
TOP_FUNCTIONS_LIMIT = 20
TOP_SENIORITIES_LIMIT = 20
TOP_SIZES_LIMIT = 20

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

def format_timestamp(ms_timestamp) -> str:
    if not ms_timestamp:
        return None
    try:
        return datetime.fromtimestamp(int(ms_timestamp) / 1000.0, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        return None

def format_api_date(date_obj) -> str:
    if not date_obj:
        return None
    year = date_obj.get("year")
    month = date_obj.get("month")
    day = date_obj.get("day")
    if year and month and day:
        return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
    return None

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

def calculate_metrics(raw: dict) -> dict:
    """Calculates rates, ratios, and down-funnel costs based on raw tracking data."""
    calc = {}
    
    impressions = raw.get("impressions", 0)
    clicks = raw.get("clicks", 0)
    landing_clicks = raw.get("landingPageClicks", 0)
    spend = raw.get("spend_float", 0.0)
    conversions = raw.get("externalWebsiteConversions", 0)
    form_opens = raw.get("oneClickLeadFormOpens", 0)
    leads = raw.get("oneClickLeads", 0)
    qual_leads = raw.get("qualifiedLeads", 0)
    v_starts = raw.get("videoStarts", 0)
    v_views = raw.get("videoViews", 0)
    v_comps = raw.get("videoCompletions", 0)

    calc["ctr_percent"] = round((clicks / impressions) * 100, 2) if impressions > 0 else 0.0
    calc["conversion_rate_percent"] = round((conversions / landing_clicks) * 100, 2) if landing_clicks > 0 else 0.0
    calc["cost_per_conversion"] = round(spend / conversions, 2) if conversions > 0 else 0.0
    calc["lead_form_completion_rate_percent"] = round((leads / form_opens) * 100, 2) if form_opens > 0 else 0.0
    calc["cost_per_lead"] = round(spend / leads, 2) if leads > 0 else 0.0
    calc["cost_per_qualified_lead"] = round(spend / qual_leads, 2) if qual_leads > 0 else 0.0
    calc["video_view_rate_percent"] = round((v_views / impressions) * 100, 2) if impressions > 0 else 0.0
    calc["video_completion_rate_percent"] = round((v_comps / v_starts) * 100, 2) if v_starts > 0 else 0.0
    calc["cpc"] = round(spend / clicks, 2) if clicks > 0 else 0.0
    calc["cpm"] = round((spend / impressions) * 1000, 2) if impressions > 0 else 0.0

    return calc

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

    # --- 2. Resolve Campaign Group Name ---
    campaign_group_urn = campaign_direct_data.get("campaignGroup")
    campaign_group_name = "Unknown Group"
    if campaign_group_urn:
        group_id = extract_id(campaign_group_urn)
        print(f"├── Resolving Campaign Group details for ID: {group_id}...")
        group_url = f"{BASE_URL}adAccounts/{account_id}/adCampaignGroups/{group_id}"
        group_data = get_linkedin_raw(group_url, token)
        campaign_group_name = group_data.get("name", "Unknown Group")

    # --- 3. Handle Targeting Transformations Upfront ---
    targeting_root = campaign_direct_data.get("targetingCriteria", {})
    all_extracted_urns = extract_all_urns_from_targeting(targeting_root)
    
    if all_extracted_urns:
        dictionary_mappings = fetch_targeting_translations(all_extracted_urns, token)
        augmented_targeting = augment_targeting_criteria(targeting_root, dictionary_mappings)
    else:
        augmented_targeting = targeting_root

    # --- 4. Resolve Associated Entity Name (Organization) ---
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

    # --- 5. Format Scheduling & Cost Data ---
    run_schedule = campaign_direct_data.get("runSchedule", {})
    start_date = format_timestamp(run_schedule.get("start"))
    end_date = format_timestamp(run_schedule.get("end"))

    daily_budget_raw = campaign_direct_data.get("dailyBudget", {})
    unit_cost_raw = campaign_direct_data.get("unitCost", {})

    output_payload = {
        "campaign": {
            "campaign_id": TARGET_CAMPAIGN_ID,
            "campaign_name": campaign_direct_data.get("name"),
            "status": campaign_direct_data.get("status"),
            "campaign_group": {
                "urn": campaign_group_urn,
                "name": campaign_group_name
            },
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
            "creatives": [],
            "company_demographics": [],
            "job_function_demographics": [],
            "seniority_demographics": [],
            "company_size_demographics": []
        }
    }

    # --- 6. Fetch Child Creatives ---
    print("├── Crawling for all associated child creatives...")
    creatives_url = (
        f"{BASE_URL}adAccounts/{account_id}/creatives"
        f"?q=criteria"
        f"&campaigns=List({campaign_urn_encoded})"
    )
    creatives_data = get_linkedin_raw(creatives_url, token)
    creative_elements = creatives_data.get("elements", []) if isinstance(creatives_data, dict) else []

    # --- 7. Fetch Global Analytics Metrics via Dual-Query Engine ---
    print("├── Dumping statistical engine analytics rows via safe chunking requests...")
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=1095)
    date_range_str = f"(start:(year:{start_dt.year},month:{start_dt.month},day:{start_dt.day}),end:(year:{end_dt.year},month:{end_dt.month},day:{end_dt.day}))"
    
    # Batch 1 (11 metrics + 2 structural fields = 13 parameters)
    metrics_batch_1 = "impressions,costInLocalCurrency,clicks,landingPageClicks,likes,shares,comments,commentLikes,totalEngagements,follows,oneClickLeadFormOpens,dateRange,pivotValues"
    # Batch 2 (8 metrics + 2 structural fields = 10 parameters)
    metrics_batch_2 = "oneClickLeads,qualifiedLeads,videoStarts,videoViews,videoCompletions,videoWatchTime,averageVideoWatchTime,externalWebsiteConversions,registrations,dateRange,pivotValues"

    stats_url_1 = f"{BASE_URL}adAnalytics?q=analytics&pivot=CREATIVE&timeGranularity=ALL&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={metrics_batch_1}"
    stats_url_2 = f"{BASE_URL}adAnalytics?q=analytics&pivot=CREATIVE&timeGranularity=ALL&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={metrics_batch_2}"

    analytics_data_1 = get_linkedin_raw(stats_url_1, token).get("elements", [])
    analytics_data_2 = get_linkedin_raw(stats_url_2, token).get("elements", [])

    performance_map = {}
    
    # Process and seed tracking data using batch 1
    for row in analytics_data_1:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            c_id = extract_id(p_vals[0])
            performance_map[c_id] = dict(row)

    # Seamlessly overlay metric components returned from batch 2
    for row in analytics_data_2:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            c_id = extract_id(p_vals[0])
            if c_id in performance_map:
                performance_map[c_id].update(row)
            else:
                performance_map[c_id] = dict(row)

    # --- 8. Assemble Hierarchical Creative Blocks ---
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
            
            image_urn = None
            image_url = None
            content_details = raw_post.get("content", {})
            
            if "article" in content_details:
                image_urn = content_details["article"].get("thumbnail")
            elif "mediaComponent" in content_details:
                image_urn = content_details["mediaComponent"].get("thumbnail")

            if image_urn:
                print(f"│   │   ├── Resolving back-end image asset location for: {image_urn}...")
                escaped_image_urn = image_urn.replace(":", "%3A")
                image_lookup_url = f"{BASE_URL}images/{escaped_image_urn}"
                raw_image_data = get_linkedin_raw(image_lookup_url, token)
                image_url = raw_image_data.get("downloadUrl")

            post_data = {
                "post_id": raw_post.get("id"),
                "publish_date": format_timestamp(raw_post.get("publishedAt")),
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
        
        raw_spend = perf_row.get("costInLocalCurrency", 0)
        spend_float = round(float(raw_spend), 2) if raw_spend else 0.0

        # Core payload mapped exactly to native API naming parameters
        performance_raw = {
            "impressions": perf_row.get("impressions", 0),
            "costInLocalCurrency": str(raw_spend),
            "spend_float": spend_float,  # Pass inside cleanly to fuel calculations
            "clicks": perf_row.get("clicks", 0),
            "landingPageClicks": perf_row.get("landingPageClicks", 0),
            "likes": perf_row.get("likes", 0),
            "shares": perf_row.get("shares", 0),
            "comments": perf_row.get("comments", 0),
            "commentLikes": perf_row.get("commentLikes", 0),
            "totalEngagements": perf_row.get("totalEngagements", 0),
            "follows": perf_row.get("follows", 0),
            "oneClickLeadFormOpens": perf_row.get("oneClickLeadFormOpens", 0),
            "oneClickLeads": perf_row.get("oneClickLeads", 0),
            "qualifiedLeads": perf_row.get("qualifiedLeads", 0),
            "videoStarts": perf_row.get("videoStarts", 0),
            "videoViews": perf_row.get("videoViews", 0),
            "videoCompletions": perf_row.get("videoCompletions", 0),
            "videoWatchTime": perf_row.get("videoWatchTime", 0),
            "averageVideoWatchTime": perf_row.get("averageVideoWatchTime", 0),
            "externalWebsiteConversions": perf_row.get("externalWebsiteConversions", 0),
            "registrations": perf_row.get("registrations", 0),
            "currency_code": output_payload["campaign"]["daily_budget"]["currency"],
            "reporting_period": {
                "start_date": format_api_date(perf_row.get("dateRange", {}).get("start")),
                "end_date": format_api_date(perf_row.get("dateRange", {}).get("end"))
            },
            "pivot_creative_urn": perf_row.get("pivotValues", [None])[0]
        }

        # Calculate ratios and downstream metrics
        performance_calculated = calculate_metrics(performance_raw)
        
        # Pop calculation helper keys out of the raw dict before outputting
        performance_raw.pop("spend_float", None)

        output_payload["campaign"]["creatives"].append({
            "creative_id": creative_id,
            "creative_name": creative.get("name"),
            "created_date": format_timestamp(creative.get("createdAt")),
            "modified_date": format_timestamp(creative.get("lastModifiedAt")),
            "post": post_data,
            "performance_raw": performance_raw,
            "performance_calculated": performance_calculated
        })

    # --- Safe Demographic Metrics ---
    demo_metrics = "dateRange,impressions,landingPageClicks,costInLocalCurrency,pivotValues"

    # --- 9. Fetch Professional Demographics Breakdown by Member Company ---
    print("├── Querying Demographics Engine for Member Companies (pivot=MEMBER_COMPANY)...")
    demo_url = (
        f"{BASE_URL}adAnalytics?q=analytics&pivot=MEMBER_COMPANY&timeGranularity=ALL"
        f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={demo_metrics}"
    )
    company_analytics = get_linkedin_raw(demo_url, token)
    
    all_companies = []
    for row in company_analytics.get("elements", []) if isinstance(company_analytics, dict) else []:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            company_urn = p_vals[0]
            row_impressions = row.get("impressions", 0)
            row_clicks = row.get("landingPageClicks", 0)
            row_ctr = round((row_clicks / row_impressions) * 100, 2) if row_impressions else 0
            
            all_companies.append({
                "company_urn": company_urn,
                "company_id": extract_id(company_urn),
                "company_name": "Name Restricted / Hidden",
                "impressions": row_impressions,
                "landing_page_clicks": row_clicks,
                "ctr_percent": row_ctr,
                "spend": round(float(row.get("costInLocalCurrency", 0)), 2) if row.get("costInLocalCurrency") else 0.0
            })

    all_companies.sort(key=lambda x: x["impressions"], reverse=True)
    company_report = all_companies[:TOP_COMPANIES_LIMIT]
    company_urn_list = [entry["company_urn"] for entry in company_report]

    if company_urn_list:
        print(f"├── Limiting company resolution tree to the top {len(company_urn_list)} records...")
        company_names = fetch_targeting_translations(company_urn_list, token)
        for entry in company_report:
            if entry["company_urn"] in company_names:
                entry["company_name"] = company_names[entry["company_urn"]]

    output_payload["campaign"]["company_demographics"] = company_report

    # --- 10. Fetch Demographics Breakdown by Job Function ---
    print("├── Querying Demographics Engine for Job Functions (pivot=MEMBER_JOB_FUNCTION)...")
    func_url = (
        f"{BASE_URL}adAnalytics?q=analytics&pivot=MEMBER_JOB_FUNCTION&timeGranularity=ALL"
        f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={demo_metrics}"
    )
    func_analytics = get_linkedin_raw(func_url, token)
    func_elements = func_analytics.get("elements", []) if isinstance(func_analytics, dict) else []

    all_functions = []
    for row in func_elements:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            func_urn = p_vals[0]
            row_impressions = row.get("impressions", 0)
            row_clicks = row.get("landingPageClicks", 0)
            row_ctr = round((row_clicks / row_impressions) * 100, 2) if row_impressions else 0
            
            all_functions.append({
                "function_urn": func_urn,
                "function_id": extract_id(func_urn),
                "function_name": "Unknown Function",
                "impressions": row_impressions,
                "landing_page_clicks": row_clicks,
                "ctr_percent": row_ctr,
                "spend": round(float(row.get("costInLocalCurrency", 0)), 2) if row.get("costInLocalCurrency") else 0.0
            })

    all_functions.sort(key=lambda x: x["impressions"], reverse=True)
    func_report = all_functions[:TOP_FUNCTIONS_LIMIT]
    func_urn_list = [entry["function_urn"] for entry in func_report]

    if func_urn_list:
        print(f"├── Resolving {len(func_urn_list)} professional job function entities...")
        func_names = fetch_targeting_translations(func_urn_list, token)
        for entry in func_report:
            if entry["function_urn"] in func_names:
                entry["function_name"] = func_names[entry["function_urn"]]

    output_payload["campaign"]["job_function_demographics"] = func_report
    print(f"│   └── Isolated top {len(func_report)} job function performance blocks.")

    # --- 11. Fetch Demographics Breakdown by Seniority ---
    print("├── Querying Demographics Engine for Member Seniority (pivot=MEMBER_SENIORITY)...")
    seniority_url = (
        f"{BASE_URL}adAnalytics?q=analytics&pivot=MEMBER_SENIORITY&timeGranularity=ALL"
        f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={demo_metrics}"
    )
    sen_analytics = get_linkedin_raw(seniority_url, token)
    sen_elements = sen_analytics.get("elements", []) if isinstance(sen_analytics, dict) else []

    all_seniorities = []
    for row in sen_elements:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            sen_urn = p_vals[0]
            row_impressions = row.get("impressions", 0)
            row_clicks = row.get("landingPageClicks", 0)
            row_ctr = round((row_clicks / row_impressions) * 100, 2) if row_impressions else 0
            
            all_seniorities.append({
                "seniority_urn": sen_urn,
                "seniority_id": extract_id(sen_urn),
                "seniority_name": "Unknown Seniority",
                "impressions": row_impressions,
                "landing_page_clicks": row_clicks,
                "ctr_percent": row_ctr,
                "spend": round(float(row.get("costInLocalCurrency", 0)), 2) if row.get("costInLocalCurrency") else 0.0
            })

    all_seniorities.sort(key=lambda x: x["impressions"], reverse=True)
    sen_report = all_seniorities[:TOP_SENIORITIES_LIMIT]
    sen_urn_list = [entry["seniority_urn"] for entry in sen_report]

    if sen_urn_list:
        print(f"├── Resolving {len(sen_urn_list)} professional seniority entities...")
        sen_names = fetch_targeting_translations(sen_urn_list, token)
        for entry in sen_report:
            if entry["seniority_urn"] in sen_names:
                entry["seniority_name"] = sen_names[entry["seniority_urn"]]

    output_payload["campaign"]["seniority_demographics"] = sen_report
    print(f"│   └── Isolated top {len(sen_report)} seniority performance blocks.")

    # --- 12. Fetch Demographics Breakdown by Company Size ---
    print("├── Querying Demographics Engine for Company Sizes (pivot=MEMBER_COMPANY_SIZE)...")
    size_url = (
        f"{BASE_URL}adAnalytics?q=analytics&pivot=MEMBER_COMPANY_SIZE&timeGranularity=ALL"
        f"&dateRange={date_range_str}&accounts=List({account_urn_encoded})&fields={demo_metrics}"
    )
    size_analytics = get_linkedin_raw(size_url, token)
    size_elements = size_analytics.get("elements", []) if isinstance(size_analytics, dict) else []

    all_sizes = []
    for row in size_elements:
        p_vals = row.get("pivotValues", [])
        if p_vals:
            size_urn = p_vals[0]
            size_id = extract_id(size_urn)
            row_impressions = row.get("impressions", 0)
            row_clicks = row.get("landingPageClicks", 0)
            row_ctr = round((row_clicks / row_impressions) * 100, 2) if row_impressions else 0
            
            all_sizes.append({
                "company_size_urn": size_urn,
                "company_size_id": size_id,
                "impressions": row_impressions,
                "landing_page_clicks": row_clicks,
                "ctr_percent": row_ctr,
                "spend": round(float(row.get("costInLocalCurrency", 0)), 2) if row.get("costInLocalCurrency") else 0.0
            })

    all_sizes.sort(key=lambda x: x["impressions"], reverse=True)
    size_report = all_sizes[:TOP_SIZES_LIMIT]

    output_payload["campaign"]["company_size_demographics"] = size_report
    print(f"│   └── Isolated top {len(size_report)} company size performance blocks.")

    # --- Write Clean Output To Disk ---
    out_file = Path(f"raw_campaign_{TARGET_CAMPAIGN_ID}_debug.json")
    out_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    print(f"\n✨ Inspection Completed! Clean nested JSON written to:\n{out_file.resolve()}\n")

if __name__ == "__main__":
    main()